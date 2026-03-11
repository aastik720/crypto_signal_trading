# ============================================
# CRYPTO SIGNAL BOT - BINANCE DATA FETCHER
# ============================================
# Fetches real-time and historical cryptocurrency
# data from Binance public API (NO key needed).
#
# Two data channels:
#   1. REST API  → historical candlestick (kline) data
#                  used for indicator calculations
#   2. WebSocket → real-time price stream for live
#                  monitoring and closed-candle events
#
# Rate limit protection:
#   - Binance allows 1200 requests/minute
#   - We throttle at 1000 requests/minute
#   - Minimum 100ms gap between REST requests
#   - WebSocket does NOT count toward limits
#
# Crash-proof design:
#   - 3 retry attempts on REST failures
#   - Auto-reconnect on WebSocket disconnect
#   - Handles Binance maintenance (503)
#   - Handles IP ban (418) with long cooldown
#   - Handles rate limit (429) with Retry-After
#   - Graceful shutdown on task cancellation
#
# Usage:
#   from data.fetcher import fetcher
#   df = await fetcher.fetch_data_for_analysis("BTCUSDT")
#   price = await fetcher.get_current_price("ETHUSDT")
# ============================================

import asyncio
import json
import time
from datetime import datetime
from collections import deque

import aiohttp
import pandas as pd
import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidURI,
    InvalidHandshake,
)

from config.settings import Config


class BinanceDataFetcher:
    """
    Async data fetcher for Binance public market data.

    Provides historical candlestick data via REST API
    and real-time price updates via WebSocket.

    All methods are async and crash-proof.
    No API key required — uses public endpoints only.

    Attributes:
        trading_pairs (list): Crypto pairs from Config
        timeframe (str):      Candle interval from Config
        latest_prices (dict): Real-time prices from WebSocket
        candle_data (dict):   Cached DataFrames per symbol
    """

    # ============================================
    # CLASS CONSTANTS
    # ============================================

    # ------ Binance API endpoints (public, free) ------
    REST_BASE_URL = "https://api.binance.com/api/v3"
    WS_BASE_URL = "wss://stream.binance.com:9443"

    # ------ Kline (candlestick) DataFrame columns ------
    # Binance returns 12 values per candle in this order
    KLINE_COLUMNS = [
        "timestamp",        # Candle open time (ms epoch)
        "open",             # Open price
        "high",             # Highest price
        "low",              # Lowest price
        "close",            # Close price
        "volume",           # Base asset volume
        "close_time",       # Candle close time (ms epoch)
        "quote_volume",     # Quote asset volume
        "trades",           # Number of trades
        "taker_buy_base",   # Taker buy base volume
        "taker_buy_quote",  # Taker buy quote volume
        "ignore",           # Unused field
    ]

    # ------ Columns that must be converted to float ------
    FLOAT_COLUMNS = [
        "open", "high", "low", "close", "volume",
        "quote_volume", "taker_buy_base", "taker_buy_quote",
    ]

    # ------ Rate limit thresholds ------
    MAX_REQUESTS_PER_MINUTE = 1000   # Throttle point (Binance allows 1200)
    MIN_REQUEST_GAP_SECONDS = 0.1    # 100ms between REST requests

    # ------ Cache duration for get_current_price ------
    PRICE_CACHE_TTL_SECONDS = 5.0

    # ------ Retry configuration ------
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 2.0

    # ------ WebSocket reconnection delay ------
    WS_RECONNECT_DELAY = 5.0

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize BinanceDataFetcher.

        Sets up:
        - Trading pairs and timeframe from Config
        - Empty dictionaries for price/candle storage
        - HTTP session placeholder (created lazily)
        - WebSocket state flags
        - Rate limiter structures
        - Price cache dictionary
        """
        # ------ Trading configuration from settings ------
        self.trading_pairs = Config.TRADING_PAIRS
        self.timeframe = Config.TIMEFRAME

        # ------ Data storage ------
        # latest_prices: updated by WebSocket in real-time
        # Key = symbol (e.g. "BTCUSDT"), Value = float price
        self.latest_prices = {}

        # candle_data: cached DataFrames from REST API
        # Key = symbol, Value = pandas DataFrame
        self.candle_data = {}

        # ------ HTTP session (created on first request) ------
        # Reused for all REST API calls for connection pooling
        self._session = None

        # ------ WebSocket state ------
        # _ws_connection: the active WebSocket object
        # _ws_running: flag to control the reconnection loop
        self._ws_connection = None
        self._ws_running = False

        # ------ Rate limiter ------
        # Deque stores timestamps of recent requests
        # _rate_lock prevents race conditions in concurrent requests
        self._request_timestamps = deque()
        self._rate_lock = asyncio.Lock()

        # ------ Price cache ------
        # Avoids hitting REST API for rapid consecutive price lookups
        # Format: {symbol: (price_float, unix_timestamp)}
        self._price_cache = {}

        print("[FETCHER] ✅ Initialized | {} pairs | {} timeframe".format(
            len(self.trading_pairs), self.timeframe
        ))

    # ============================================
    # PRIVATE HELPERS
    # ============================================

    async def _get_session(self):
        """
        Returns an active aiohttp ClientSession.

        Creates a new session if none exists or if the
        previous one was closed. The session is reused
        across all REST API calls for efficiency
        (HTTP connection pooling).

        Configured with:
        - 30 second total timeout per request
        - JSON Accept header
        - Connection limit of 20 simultaneous connections

        Returns:
            aiohttp.ClientSession: Ready-to-use HTTP session
        """
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(
                limit=20,            # Max 20 simultaneous connections
                limit_per_host=10,   # Max 10 to same host
                ttl_dns_cache=300,   # Cache DNS for 5 minutes
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"Accept": "application/json"},
            )
            print("[FETCHER] HTTP session created")

        return self._session

    async def _close_session(self):
        """
        Safely closes the aiohttp HTTP session.

        Called during shutdown to release all HTTP
        connections and free resources.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            # Allow time for SSL connections to close properly
            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            await asyncio.sleep(0.25)
            self._session = None
            print("[FETCHER] HTTP session closed")

    async def _rate_limit_wait(self):
        """
        Enforces Binance rate limits before each REST request.

        Strategy:
        1. Acquire lock (prevents concurrent rate checks)
        2. Remove request timestamps older than 60 seconds
        3. If count >= 1000, wait until oldest falls out of window
        4. Enforce minimum 100ms gap between requests
        5. Record current request timestamp
        6. Release lock

        This is called BEFORE every REST API request.
        WebSocket messages do NOT pass through this.
        """
        async with self._rate_lock:
            now = time.time()

            # ------ Step 1: Clean expired timestamps ------
            # Remove entries older than 60 seconds
            while (self._request_timestamps and
                   self._request_timestamps[0] < now - 60):
                self._request_timestamps.popleft()

            # ------ Step 2: Check if approaching limit ------
            current_count = len(self._request_timestamps)

            if current_count >= self.MAX_REQUESTS_PER_MINUTE:
                # Calculate how long to wait
                oldest = self._request_timestamps[0]
                wait_time = 60.0 - (now - oldest) + 0.5  # +0.5s safety buffer
                if wait_time > 0:
                    print("[FETCHER] ⚠️ Rate limit: {}/{} req/min | "
                          "Throttling for {:.1f}s".format(
                              current_count,
                              self.MAX_REQUESTS_PER_MINUTE,
                              wait_time
                          ))
                    await asyncio.sleep(wait_time)

            # ------ Step 3: Enforce minimum gap ------
            if self._request_timestamps:
                elapsed = time.time() - self._request_timestamps[-1]
                if elapsed < self.MIN_REQUEST_GAP_SECONDS:
                    gap = self.MIN_REQUEST_GAP_SECONDS - elapsed
                    await asyncio.sleep(gap)

            # ------ Step 4: Record this request ------
            self._request_timestamps.append(time.time())

    async def _process_ws_message(self, raw_message, callback_function):
        """
        Processes a single WebSocket message from Binance.

        Combined stream messages arrive in this format:
        {
            "stream": "btcusdt@kline_5m",
            "data": {
                "e": "kline",
                "s": "BTCUSDT",
                "k": {
                    "o": "42000.00",   (open)
                    "h": "42100.00",   (high)
                    "l": "41900.00",   (low)
                    "c": "42050.00",   (close)
                    "v": "100.5",      (volume)
                    "x": true/false,   (is candle closed?)
                    "t": 1638747600000 (candle open timestamp)
                }
            }
        }

        On EVERY message: updates latest_prices dict.
        On CLOSED candle (x=True): calls the callback function
        with a clean dictionary of candle data.

        Args:
            raw_message (str):       Raw JSON string from WebSocket
            callback_function:       Async/sync function to call on candle close
        """
        try:
            message = json.loads(raw_message)

            # ------ Extract from combined stream wrapper ------
            # Combined streams wrap data in {"stream": ..., "data": ...}
            if "stream" in message and "data" in message:
                event_data = message["data"]
            else:
                # Single stream format (no wrapper)
                event_data = message

            # ------ Verify this is a kline event ------
            if event_data.get("e") != "kline":
                return

            # ------ Extract kline data ------
            kline = event_data["k"]
            symbol = kline["s"]                    # e.g. "BTCUSDT"
            close_price = float(kline["c"])         # Current close price
            is_candle_closed = kline["x"]           # True when candle finalizes

            # ------ Update latest price (every tick) ------
            self.latest_prices[symbol] = close_price

            # ------ On closed candle: trigger callback ------
            if is_candle_closed:
                candle_info = {
                    "symbol": symbol,
                    "timestamp": kline["t"],           # Open time (ms epoch)
                    "open": float(kline["o"]),
                    "high": float(kline["h"]),
                    "low": float(kline["l"]),
                    "close": close_price,
                    "volume": float(kline["v"]),
                    "quote_volume": float(kline["q"]),
                    "trades": int(kline["n"]),
                    "is_closed": True,
                }

                print("[FETCHER] 🕯️ Candle closed: {} | O:{:.2f} H:{:.2f} "
                      "L:{:.2f} C:{:.2f} V:{:.2f}".format(
                          symbol,
                          candle_info["open"],
                          candle_info["high"],
                          candle_info["low"],
                          candle_info["close"],
                          candle_info["volume"],
                      ))

                # Call the callback (supports both async and sync)
                if callback_function is not None:
                    if asyncio.iscoroutinefunction(callback_function):
                        await callback_function(candle_info)
                    else:
                        callback_function(candle_info)

        except json.JSONDecodeError:
            print("[FETCHER] ⚠️ Invalid JSON from WebSocket")

        except KeyError as e:
            print("[FETCHER] ⚠️ Missing key in WebSocket data: {}".format(e))

        except (ValueError, TypeError) as e:
            print("[FETCHER] ⚠️ Data conversion error in WebSocket: {}".format(e))

        except Exception as e:
            print("[FETCHER] ⚠️ WebSocket message processing error: {}".format(e))

    # ============================================
    # FUNCTION 2: GET KLINES (Historical Candles)
    # ============================================

    async def get_klines(self, symbol, interval=None, limit=100):
        """
        Fetches historical candlestick data from Binance REST API.

        Makes a GET request to /api/v3/klines endpoint.
        Returns data as a pandas DataFrame with proper types.

        Retry logic: 3 attempts with 2-second delay between.
        Special handling for:
        - HTTP 429 (rate limited): waits Retry-After seconds
        - HTTP 418 (IP banned): waits 5 minutes
        - HTTP 503 (maintenance): waits 30 seconds
        - Timeout: retries with standard delay

        Args:
            symbol (str):   Trading pair, e.g. "BTCUSDT"
            interval (str): Candle interval, e.g. "5m", "1h"
                           Defaults to Config.TIMEFRAME
            limit (int):    Number of candles (max 1000)

        Returns:
            pandas.DataFrame: Candlestick data with columns:
                [timestamp, open, high, low, close, volume,
                 close_time, quote_volume, trades,
                 taker_buy_base, taker_buy_quote, ignore]
                All price columns are float type.
                timestamp and close_time are datetime type.
            None: If all retry attempts failed.
        """
        # Use Config timeframe if not specified
        if interval is None:
            interval = self.timeframe

        # Build request URL and parameters
        url = "{}/klines".format(self.REST_BASE_URL)
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }

        # ------ Retry loop: 3 attempts ------
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Respect rate limits before making request
                await self._rate_limit_wait()

                # Get or create HTTP session
                session = await self._get_session()

                async with session.get(url, params=params) as response:

                    # ---- SUCCESS: HTTP 200 ----
                    if response.status == 200:
                        raw_data = await response.json()

                        # Validate response is not empty
                        if not raw_data:
                            print("[FETCHER] ⚠️ Empty klines response for {}".format(
                                symbol
                            ))
                            return None

                        # ---- Build DataFrame ----
                        df = pd.DataFrame(raw_data, columns=self.KLINE_COLUMNS)

                        # ---- Convert price/volume columns to float ----
                        # Binance returns these as strings for precision
                        for col in self.FLOAT_COLUMNS:
                            df[col] = pd.to_numeric(df[col], errors="coerce")

                        # ---- Convert trades count to integer ----
                        df["trades"] = pd.to_numeric(
                            df["trades"], errors="coerce"
                        ).fillna(0).astype(int)

                        # ---- Convert timestamps to datetime ----
                        df["timestamp"] = pd.to_datetime(
                            df["timestamp"], unit="ms", utc=True
                        )
                        df["close_time"] = pd.to_datetime(
                            df["close_time"], unit="ms", utc=True
                        )

                        # ---- Sort by time (oldest first) ----
                        df = df.sort_values("timestamp").reset_index(drop=True)

                        # ---- Drop any rows with NaN in critical columns ----
                        critical_cols = ["open", "high", "low", "close", "volume"]
                        df = df.dropna(subset=critical_cols)

                        print("[FETCHER] ✅ Klines fetched: {} | {} candles | "
                              "interval={}".format(symbol, len(df), interval))

                        return df

                    # ---- RATE LIMITED: HTTP 429 ----
                    elif response.status == 429:
                        # Binance provides Retry-After header (in seconds)
                        retry_after = int(
                            response.headers.get("Retry-After", 60)
                        )
                        print("[FETCHER] ⚠️ Rate limited (429) for {} | "
                              "Waiting {}s (attempt {}/{})".format(
                                  symbol, retry_after, attempt,
                                  self.MAX_RETRIES
                              ))
                        await asyncio.sleep(retry_after)
                        continue

                    # ---- IP BANNED: HTTP 418 ----
                    elif response.status == 418:
                        # Severe rate limit violation — IP temporarily banned
                        retry_after = int(
                            response.headers.get("Retry-After", 300)
                        )
                        print("[FETCHER] 🚫 IP BANNED (418) by Binance! "
                              "Waiting {}s".format(retry_after))
                        await asyncio.sleep(retry_after)
                        continue

                    # ---- MAINTENANCE: HTTP 503 ----
                    elif response.status == 503:
                        print("[FETCHER] 🔧 Binance maintenance (503) | "
                              "Waiting 30s (attempt {}/{})".format(
                                  attempt, self.MAX_RETRIES
                              ))
                        await asyncio.sleep(30)
                        continue

                    # ---- OTHER HTTP ERRORS ----
                    else:
                        error_text = await response.text()
                        print("[FETCHER] ❌ HTTP {} for {} | "
                              "Response: {} (attempt {}/{})".format(
                                  response.status, symbol,
                                  error_text[:200], attempt,
                                  self.MAX_RETRIES
                              ))
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(self.RETRY_DELAY_SECONDS)
                        continue

            # ---- TIMEOUT ----
            except asyncio.TimeoutError:
                print("[FETCHER] ⏱️ Timeout fetching klines for {} "
                      "(attempt {}/{})".format(
                          symbol, attempt, self.MAX_RETRIES
                      ))
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)

            # ---- CONNECTION ERROR ----
            except aiohttp.ClientError as e:
                print("[FETCHER] 🔌 Connection error for {} "
                      "(attempt {}/{}): {}".format(
                          symbol, attempt, self.MAX_RETRIES, e
                      ))
                # Recreate session on connection errors
                await self._close_session()
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)

            # ---- UNEXPECTED ERROR ----
            except Exception as e:
                print("[FETCHER] ❌ Unexpected error fetching {} "
                      "(attempt {}/{}): {}".format(
                          symbol, attempt, self.MAX_RETRIES, e
                      ))
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)

        # All attempts exhausted
        print("[FETCHER] ❌ FAILED to fetch klines for {} "
              "after {} attempts".format(symbol, self.MAX_RETRIES))
        return None

    # ============================================
    # FUNCTION 3: GET CURRENT PRICE
    # ============================================

    async def get_current_price(self, symbol):
        """
        Fetches the current market price for a single symbol.

        Uses /api/v3/ticker/price endpoint.
        Results are cached for 5 seconds to prevent
        excessive API calls for rapid lookups.

        Check order:
        1. Price cache (if < 5 seconds old)
        2. WebSocket latest_prices (always fresh)
        3. REST API call (fallback)

        Args:
            symbol (str): Trading pair, e.g. "BTCUSDT"

        Returns:
            float: Current price, or None on failure
        """
        symbol = symbol.upper()

        # ------ Check 1: Price cache ------
        if symbol in self._price_cache:
            cached_price, cached_time = self._price_cache[symbol]
            age = time.time() - cached_time
            if age < self.PRICE_CACHE_TTL_SECONDS:
                return cached_price

        # ------ Check 2: WebSocket latest prices ------
        # If WebSocket is running, this is the freshest data
        if symbol in self.latest_prices:
            ws_price = self.latest_prices[symbol]
            # Update cache with WebSocket price
            self._price_cache[symbol] = (ws_price, time.time())
            return ws_price

        # ------ Check 3: REST API call ------
        url = "{}/ticker/price".format(self.REST_BASE_URL)
        params = {"symbol": symbol}

        try:
            await self._rate_limit_wait()
            session = await self._get_session()

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])

                    # Update both caches
                    self._price_cache[symbol] = (price, time.time())
                    self.latest_prices[symbol] = price

                    print("[FETCHER] 💰 Price fetched: {} = ${:,.2f}".format(
                        symbol, price
                    ))
                    return price

                else:
                    error_text = await response.text()
                    print("[FETCHER] ❌ Price fetch failed for {} | "
                          "HTTP {}: {}".format(
                              symbol, response.status, error_text[:200]
                          ))
                    return None

        except asyncio.TimeoutError:
            print("[FETCHER] ⏱️ Timeout fetching price for {}".format(symbol))
            return None

        except aiohttp.ClientError as e:
            print("[FETCHER] 🔌 Connection error fetching price "
                  "for {}: {}".format(symbol, e))
            return None

        except (ValueError, KeyError) as e:
            print("[FETCHER] ❌ Invalid price data for {}: {}".format(
                symbol, e
            ))
            return None

        except Exception as e:
            print("[FETCHER] ❌ Unexpected error fetching price "
                  "for {}: {}".format(symbol, e))
            return None

    # ============================================
    # FUNCTION 4: GET ALL PAIRS DATA
    # ============================================

    async def get_all_pairs_data(self):
        """
        Fetches kline data for ALL trading pairs in Config.

        Iterates through TRADING_PAIRS, fetching 100 candles
        of 5-minute data for each. Adds a 200ms delay between
        requests to respect rate limits.

        Failed fetches are skipped (logged but not fatal).
        The bot continues with whatever data it could get.

        Stores results in self.candle_data for caching.

        Returns:
            dict: {symbol: DataFrame} for all successfully
                  fetched pairs. Empty dict if all failed.
        """
        all_data = {}
        success_count = 0
        fail_count = 0

        print("[FETCHER] 📡 Fetching data for {} pairs...".format(
            len(self.trading_pairs)
        ))

        for symbol in self.trading_pairs:
            try:
                # Fetch 100 candles of configured timeframe
                df = await self.get_klines(
                    symbol=symbol,
                    interval=self.timeframe,
                    limit=100
                )

                if df is not None and not df.empty:
                    all_data[symbol] = df
                    self.candle_data[symbol] = df
                    success_count += 1
                else:
                    print("[FETCHER] ⚠️ No data returned for {}, "
                          "skipping".format(symbol))
                    fail_count += 1

                # 200ms delay between requests to be respectful
                await asyncio.sleep(0.2)

            except Exception as e:
                print("[FETCHER] ❌ Error fetching {}: {}".format(symbol, e))
                fail_count += 1
                # Continue with next pair — don't stop the loop
                await asyncio.sleep(0.2)
                continue

        print("[FETCHER] 📊 Fetch complete: {}/{} pairs succeeded, "
              "{} failed".format(
                  success_count, len(self.trading_pairs), fail_count
              ))

        return all_data

    # ============================================
    # FUNCTION 5: START WEBSOCKET
    # ============================================

    async def start_websocket(self, callback_function=None):
        """
        Connects to Binance WebSocket and streams real-time data.

        Subscribes to kline (candlestick) streams for ALL
        trading pairs using a single combined connection.

        Combined stream URL format:
        wss://stream.binance.com:9443/stream?streams=
        btcusdt@kline_5m/ethusdt@kline_5m/...

        Behavior:
        - On EVERY tick: updates self.latest_prices
        - On CLOSED candle: calls callback_function(candle_data)
        - On disconnect: auto-reconnects after 5 seconds
        - On error: logs and continues
        - On stop_websocket(): breaks loop cleanly

        This is a LONG-RUNNING coroutine. Call it with:
            asyncio.create_task(fetcher.start_websocket(my_callback))

        It runs until stop_websocket() is called.

        Args:
            callback_function: Async or sync function called when
                              a candle closes. Receives dict:
                              {symbol, timestamp, open, high,
                               low, close, volume, ...}
        """
        # Prevent duplicate WebSocket connections
        if self._ws_running:
            print("[FETCHER] ⚠️ WebSocket already running — ignoring start")
            return

        self._ws_running = True

        # ------ Build combined stream URL ------
        # Each pair gets its own kline stream
        # All combined into one WebSocket connection
        streams = "/".join([
            "{}@kline_{}".format(pair.lower(), self.timeframe)
            for pair in self.trading_pairs
        ])
        ws_url = "{}/stream?streams={}".format(self.WS_BASE_URL, streams)

        print("[FETCHER] 🌐 WebSocket URL: {}...".format(ws_url[:80]))
        print("[FETCHER] 🌐 Subscribing to {} kline streams".format(
            len(self.trading_pairs)
        ))

        # ------ Reconnection loop ------
        # Keeps reconnecting until stop_websocket() is called
        reconnect_count = 0

        while self._ws_running:
            try:
                # Open WebSocket connection with keepalive pings
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,    # Send ping every 20s
                    ping_timeout=20,     # Wait 20s for pong
                    close_timeout=10,    # Wait 10s on close
                    max_size=2 ** 20,    # 1MB max message size
                ) as ws:

                    # Store reference for stop_websocket()
                    self._ws_connection = ws
                    reconnect_count = 0  # Reset on successful connect

                    print("[FETCHER] ✅ WebSocket CONNECTED | "
                          "Streaming {} pairs".format(
                              len(self.trading_pairs)
                          ))

                    # ------ Message receive loop ------
                    async for raw_message in ws:
                        # Check shutdown flag
                        if not self._ws_running:
                            print("[FETCHER] 🛑 WebSocket shutdown requested")
                            break

                        # Process the incoming message
                        await self._process_ws_message(
                            raw_message, callback_function
                        )

            # ---- Normal close (e.g. Binance 24h rotation) ----
            except ConnectionClosedOK:
                if self._ws_running:
                    reconnect_count += 1
                    print("[FETCHER] 🔄 WebSocket closed normally | "
                          "Reconnecting in {}s (attempt #{})".format(
                              self.WS_RECONNECT_DELAY, reconnect_count
                          ))
                    await asyncio.sleep(self.WS_RECONNECT_DELAY)

            # ---- Abnormal close (server error, network drop) ----
            except ConnectionClosedError as e:
                if self._ws_running:
                    reconnect_count += 1
                    print("[FETCHER] ⚠️ WebSocket closed with error: {} | "
                          "Reconnecting in {}s (attempt #{})".format(
                              e, self.WS_RECONNECT_DELAY, reconnect_count
                          ))
                    await asyncio.sleep(self.WS_RECONNECT_DELAY)

            # ---- Any connection closed ----
            except ConnectionClosed as e:
                if self._ws_running:
                    reconnect_count += 1
                    print("[FETCHER] 🔌 WebSocket disconnected: {} | "
                          "Reconnecting in {}s (attempt #{})".format(
                              e, self.WS_RECONNECT_DELAY, reconnect_count
                          ))
                    await asyncio.sleep(self.WS_RECONNECT_DELAY)

            # ---- Invalid WebSocket URI ----
            except InvalidURI as e:
                print("[FETCHER] ❌ Invalid WebSocket URI: {}".format(e))
                self._ws_running = False
                break

            # ---- Handshake failure ----
            except InvalidHandshake as e:
                if self._ws_running:
                    reconnect_count += 1
                    print("[FETCHER] 🤝 WebSocket handshake failed: {} | "
                          "Reconnecting in {}s (attempt #{})".format(
                              e, self.WS_RECONNECT_DELAY * 2, reconnect_count
                          ))
                    # Double delay for handshake failures
                    await asyncio.sleep(self.WS_RECONNECT_DELAY * 2)

            # ---- Task cancelled (bot shutting down) ----
            except asyncio.CancelledError:
                print("[FETCHER] 🛑 WebSocket task CANCELLED")
                self._ws_running = False
                break

            # ---- Internet down / DNS failure / other ----
            except OSError as e:
                if self._ws_running:
                    reconnect_count += 1
                    # Exponential backoff: 5s, 10s, 20s, max 60s
                    delay = min(
                        self.WS_RECONNECT_DELAY * (2 ** min(reconnect_count - 1, 3)),
                        60.0
                    )
                    print("[FETCHER] 🌐 Network error: {} | "
                          "Reconnecting in {:.0f}s (attempt #{})".format(
                              e, delay, reconnect_count
                          ))
                    await asyncio.sleep(delay)

            # ---- Catch-all for unexpected errors ----
            except Exception as e:
                if self._ws_running:
                    reconnect_count += 1
                    delay = min(
                        self.WS_RECONNECT_DELAY * (2 ** min(reconnect_count - 1, 3)),
                        60.0
                    )
                    print("[FETCHER] ❌ Unexpected WebSocket error: {} | "
                          "Type: {} | Reconnecting in {:.0f}s "
                          "(attempt #{})".format(
                              e, type(e).__name__, delay, reconnect_count
                          ))
                    await asyncio.sleep(delay)

            finally:
                # Clear connection reference
                self._ws_connection = None

        # ------ Loop exited ------
        self._ws_running = False
        self._ws_connection = None
        print("[FETCHER] 🛑 WebSocket STOPPED")

    # ============================================
    # FUNCTION 6: STOP WEBSOCKET
    # ============================================

    async def stop_websocket(self):
        """
        Gracefully stops the WebSocket connection.

        Sets _ws_running to False, which causes the
        reconnection loop in start_websocket() to exit.
        Then closes the active WebSocket connection.

        Safe to call even if WebSocket is not running.
        """
        print("[FETCHER] 🛑 Stopping WebSocket...")

        # Signal the reconnection loop to stop
        self._ws_running = False

        # Close the active WebSocket connection
        if self._ws_connection is not None:
            try:
                await self._ws_connection.close()
                print("[FETCHER] WebSocket connection closed")
            except Exception as e:
                print("[FETCHER] ⚠️ Error closing WebSocket: {}".format(e))
            finally:
                self._ws_connection = None

    # ============================================
    # FUNCTION 7: GET LATEST PRICE (Synchronous)
    # ============================================

    def get_latest_price(self, symbol):
        """
        Returns the latest cached price for a symbol.

        This is a SYNCHRONOUS method — it only reads from
        the in-memory latest_prices dictionary. No API calls.

        The dictionary is populated by:
        - WebSocket stream (real-time updates)
        - get_current_price() REST calls (cached)

        Args:
            symbol (str): Trading pair, e.g. "BTCUSDT"

        Returns:
            float: Latest price, or None if not available
        """
        symbol = symbol.upper()

        price = self.latest_prices.get(symbol)

        if price is None:
            # Also check the REST cache as fallback
            if symbol in self._price_cache:
                cached_price, cached_time = self._price_cache[symbol]
                # Return even stale cache — better than None
                return cached_price

        return price

    # ============================================
    # FUNCTION 8: FETCH DATA FOR ANALYSIS
    # ============================================

    async def fetch_data_for_analysis(self, symbol):
        """
        Fetches clean candlestick data ready for algorithm use.

        This is the MAIN function that signal_engine.py and
        all indicator modules (RSI, MACD, Bollinger, Volume)
        will call to get their input data.

        Fetches 100 candles of 5-minute data, then:
        1. Keeps only: open, high, low, close, volume
        2. Converts all values to float
        3. Sets timestamp as the DataFrame index
        4. Drops any rows with missing data
        5. Verifies minimum data requirement

        Args:
            symbol (str): Trading pair, e.g. "BTCUSDT"

        Returns:
            pandas.DataFrame: Clean DataFrame with columns:
                [open, high, low, close, volume]
                Indexed by timestamp (datetime).
                All values are float type.
            None: If fetch failed or insufficient data.
        """
        symbol = symbol.upper()

        try:
            # ------ Fetch raw kline data ------
            df = await self.get_klines(
                symbol=symbol,
                interval=self.timeframe,
                limit=100
            )

            # ------ Validate response ------
            if df is None:
                print("[FETCHER] ❌ No data for analysis: {}".format(symbol))
                return None

            if df.empty:
                print("[FETCHER] ❌ Empty DataFrame for: {}".format(symbol))
                return None

            # ------ Extract analysis columns only ------
            analysis_columns = ["open", "high", "low", "close", "volume"]
            analysis_df = df[["timestamp"] + analysis_columns].copy()

            # ------ Set timestamp as index ------
            analysis_df.set_index("timestamp", inplace=True)

            # ------ Ensure all values are float ------
            for col in analysis_columns:
                analysis_df[col] = analysis_df[col].astype(float)

            # ------ Drop rows with any NaN values ------
            rows_before = len(analysis_df)
            analysis_df = analysis_df.dropna()
            rows_dropped = rows_before - len(analysis_df)

            if rows_dropped > 0:
                print("[FETCHER] ⚠️ Dropped {} NaN rows for {}".format(
                    rows_dropped, symbol
                ))

            # ------ Verify minimum data for indicators ------
            # RSI needs 14 periods, Bollinger needs 20, MACD needs 26
            # So we need at least 30 candles for reliable signals
            min_required = 30
            if len(analysis_df) < min_required:
                print("[FETCHER] ⚠️ Insufficient data for {}: {} candles "
                      "(need {})".format(
                          symbol, len(analysis_df), min_required
                      ))
                return None

            # ------ Cache the result ------
            self.candle_data[symbol] = analysis_df

            print("[FETCHER] 📊 Analysis data ready: {} | "
                  "{} candles | Latest close: ${:,.2f}".format(
                      symbol, len(analysis_df),
                      analysis_df["close"].iloc[-1]
                  ))

            return analysis_df

        except KeyError as e:
            print("[FETCHER] ❌ Missing column in {} data: {}".format(
                symbol, e
            ))
            return None

        except (ValueError, TypeError) as e:
            print("[FETCHER] ❌ Type conversion error for {}: {}".format(
                symbol, e
            ))
            return None

        except Exception as e:
            print("[FETCHER] ❌ Unexpected error preparing {} "
                  "analysis data: {}".format(symbol, e))
            return None

    # ============================================
    # CLEANUP METHOD
    # ============================================

    async def close(self):
        """
        Shuts down all connections cleanly.

        Stops WebSocket stream and closes HTTP session.
        Call this when the bot is shutting down.

        Safe to call multiple times.
        """
        print("[FETCHER] 🧹 Closing all connections...")
        await self.stop_websocket()
        await self._close_session()
        print("[FETCHER] ✅ All connections closed")


# ==================================================
# MODULE-LEVEL SINGLETON INSTANCE
# ==================================================
# This is THE fetcher object used across the entire bot.
# Every module imports this same instance:
#
#   from data.fetcher import fetcher
#   df = await fetcher.fetch_data_for_analysis("BTCUSDT")
#   price = await fetcher.get_current_price("ETHUSDT")
#   asyncio.create_task(fetcher.start_websocket(callback))
#
# Only ONE instance exists — all operations share the
# same HTTP session, rate limiter, and WebSocket.
# ==================================================

fetcher = BinanceDataFetcher()

# ==================================================
# MODULE LOAD CONFIRMATION
# ==================================================
print("[FETCHER] ✅ Data fetcher module loaded and ready")