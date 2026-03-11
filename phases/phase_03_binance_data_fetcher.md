PROMPT FOR PHASE 3:
====================

Project: CryptoSignal Bot (continuing from Phase 1-2)
Task: Build the Binance data fetcher in data/fetcher.py

CONTEXT: This bot needs REAL-TIME crypto price data from 
Binance. Binance provides FREE WebSocket and REST API for 
market data (no API key needed for public data).

We need two types of data:
1. Real-time price via WebSocket (for live monitoring)
2. Historical candlestick data via REST API (for calculating 
   RSI, MACD, Bollinger Bands, Volume)

The config/settings.py has TRADING_PAIRS list and TIMEFRAME.

BUILD data/fetcher.py with these EXACT specifications:

BINANCE API ENDPOINTS (FREE, NO KEY NEEDED):
- WebSocket: wss://stream.binance.com:9443/ws/
- REST Klines: https://api.binance.com/api/v3/klines
- REST Ticker: https://api.binance.com/api/v3/ticker/price

CLASS: BinanceDataFetcher

FUNCTIONS NEEDED:

1. __init__(self)
   - Initialize with trading pairs from Config
   - Store latest prices dictionary
   - Store candlestick data dictionary
   - Set connection status flags

2. async get_klines(self, symbol, interval="5m", limit=100)
   - Fetch historical candlestick data from Binance REST API
   - Parameters: symbol (like "BTCUSDT"), interval, limit
   - Returns pandas DataFrame with columns:
     [timestamp, open, high, low, close, volume, 
      close_time, quote_volume, trades, 
      taker_buy_base, taker_buy_quote, ignore]
   - Convert all price columns to float
   - Convert timestamp to datetime
   - Handle errors gracefully
   - Add retry logic (3 attempts with 2 second delay)

3. async get_current_price(self, symbol)
   - Fetch current price from REST API
   - Returns float price
   - Cache result for 5 seconds to avoid rate limiting

4. async get_all_pairs_data(self)
   - Loop through all TRADING_PAIRS from Config
   - Fetch klines for each pair
   - Store in dictionary: {symbol: dataframe}
   - Return the complete dictionary
   - Add 200ms delay between requests to respect rate limits

5. async start_websocket(self, callback_function)
   - Connect to Binance WebSocket
   - Subscribe to all TRADING_PAIRS mini ticker stream
   - Stream URL format: 
     wss://stream.binance.com:9443/ws/btcusdt@kline_5m
   - Combined stream for multiple pairs:
     wss://stream.binance.com:9443/stream?streams=
     btcusdt@kline_5m/ethusdt@kline_5m/...
   - On each message: update latest_prices dictionary
   - On each closed candle: call callback_function with 
     the candle data
   - Handle disconnection: auto-reconnect after 5 seconds
   - Handle errors: log and continue

6. async stop_websocket(self)
   - Gracefully close WebSocket connection
   - Set connection status to False

7. def get_latest_price(self, symbol)
   - Return latest cached price for symbol
   - Return None if not available

8. async fetch_data_for_analysis(self, symbol)
   - This is the MAIN function other modules will call
   - Fetches 100 candles of 5m data for given symbol
   - Returns clean pandas DataFrame ready for algorithm use
   - DataFrame must have: open, high, low, close, volume
   - All as float type
   - Indexed by timestamp

IMPORTANT REQUIREMENTS:
- Use aiohttp for REST API calls (async)
- Use websockets library for WebSocket connection
- NO Binance API key needed (public data only)
- Rate limit protection: max 1200 requests per minute
- Add request counter and automatic throttling
- All functions must be async
- Proper error handling everywhere
- Log all connections, disconnections, errors
- Import Config from config.settings
- Import logger from utils.logger (just use print for now 
  if logger not built yet)

RATE LIMIT SAFETY:
- Add a request counter
- If approaching 1000 requests/minute, slow down
- Add minimum 100ms between consecutive REST requests
- WebSocket doesn't count toward rate limits

Make it production-ready. This must run 24/7 without crashing.
Must handle Binance server maintenance gracefully.
Must handle internet disconnection and auto-reconnect.