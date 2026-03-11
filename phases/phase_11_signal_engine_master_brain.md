PROMPT FOR PHASE 8:

PROJECT: CryptoSignal Bot
PHASE: 8 - Signal Engine (Combines All 4 Brains)

Create file: algorithms/signal_engine.py

PURPOSE:
This is the MOST IMPORTANT file in the entire project.
It takes outputs from all 4 brains (RSI, MACD, Bollinger, Volume)
and combines them into ONE final signal with a confidence score.
Only signals with 65%+ confidence are sent to users.

BRAIN WEIGHTS (How much each brain matters):
- RSI Weight     = 25% (0.25)
- MACD Weight    = 30% (0.30) ← slightly more because trend is king
- Bollinger Weight = 25% (0.25)
- Volume Weight  = 20% (0.20) ← confirmation role

IMPORTS:
- RSIAnalyzer from algorithms.rsi
- MACDAnalyzer from algorithms.macd
- BollingerAnalyzer from algorithms.bollinger
- VolumeAnalyzer from algorithms.volume
- BinanceDataFetcher from data.fetcher

CLASS: SignalEngine

ATTRIBUTES:
- rsi_analyzer: RSIAnalyzer instance
- macd_analyzer: MACDAnalyzer instance
- bollinger_analyzer: BollingerAnalyzer instance
- volume_analyzer: VolumeAnalyzer instance
- data_fetcher: BinanceDataFetcher instance
- signal_cooldowns: dict tracking last signal time per pair
- weights: {"rsi": 0.25, "macd": 0.30, "bollinger": 0.25, "volume": 0.20}

METHODS:

1. __init__(self, data_fetcher)
   - Initialize all 4 brain analyzers
   - Store data_fetcher reference
   - Initialize cooldown tracker
   - Initialize signal history

2. async analyze_pair(self, symbol: str) -> dict or None
   - Get data for this symbol from data_fetcher
   - If data not ready (not enough candles), return None
   - Run all 4 brains:
     a) rsi_result = rsi_analyzer.get_signal(closes)
     b) macd_result = macd_analyzer.get_signal(closes)
     c) bollinger_result = bollinger_analyzer.get_signal(closes)
     d) volume_result = volume_analyzer.get_signal(volumes, closes)
   - Pass results to combine_signals()
   - Return final signal or None

3. combine_signals(self, rsi, macd, bollinger, volume, symbol, price) -> dict or None

   THE CORE ALGORITHM:

   Step 1: Calculate Weighted Score
   weighted_score = (rsi["score"] * 0.25) +
                    (macd["score"] * 0.30) +
                    (bollinger["score"] * 0.25) +
                    (volume["score"] * 0.20)

   Step 2: Determine Direction
   - If weighted_score > 55 → direction = "LONG"
   - If weighted_score < 45 → direction = "SHORT"
   - If 45 <= weighted_score <= 55 → direction = "NEUTRAL" (skip)

   Step 3: Calculate Confidence
   Base confidence = how far the score is from 50
   For LONG: confidence = min(((weighted_score - 50) / 50) * 100, 100)
   For SHORT: confidence = min(((50 - weighted_score) / 50) * 100, 100)

   Step 4: Agreement Bonus
   Count how many brains agree on direction:
   - If 4/4 brains agree → add 15% to confidence
   - If 3/4 brains agree → add 8% to confidence
   - If 2/4 brains agree → no bonus
   - If 1/4 or 0/4 → subtract 10% from confidence (conflicting signals)

   Step 5: Special Bonuses
   - If RSI shows divergence → add 5% to confidence
   - If MACD just had crossover → add 5% to confidence
   - If Bollinger squeeze releasing → add 5% to confidence
   - If Volume spike confirms direction → add 5% to confidence
   - Maximum total confidence = 95% (never say 100%)

   Step 6: Minimum Confidence Check
   - If final confidence < 65% → return None (don't send signal)
   - Only signals with 65%+ confidence are worth sending

   Step 7: Cooldown Check
   - Check if we sent a signal for this pair in last 10 minutes
   - If yes, return None (prevent spam)
   - If no, update cooldown tracker

   Step 8: Calculate Entry, Targets, Stop Loss
   current_price = latest close price

   For LONG signals:
   - entry_price = current_price
   - stop_loss = current_price * (1 - STOP_LOSS_PERCENT/100)
   - target_1 = current_price * (1 + TARGET_1_PERCENT/100)
   - target_2 = current_price * (1 + TARGET_2_PERCENT/100)

   For SHORT signals:
   - entry_price = current_price
   - stop_loss = current_price * (1 + STOP_LOSS_PERCENT/100)
   - target_1 = current_price * (1 - TARGET_1_PERCENT/100)
   - target_2 = current_price * (1 - TARGET_2_PERCENT/100)

   DYNAMIC STOP LOSS AND TARGETS (ADVANCED):
   - Use Bollinger Bands for smarter levels:
   - For LONG:
     - Stop Loss = max(lower_band, current_price * 0.99)
     - Target 1 = min(middle_band, current_price * 1.02)
       if price is below middle band
     - Target 2 = upper_band
   - For SHORT: opposite logic

   Step 9: Build Final Signal
   {
       "pair": "BTC/USDT",
       "direction": "LONG" / "SHORT",
       "entry_price": 43250.00,
       "target_1": 44100.00,
       "target_2": 45500.00,
       "stop_loss": 42800.00,
       "confidence": 78,
       "rsi_score": rsi["score"],
       "macd_score": macd["score"],
       "bollinger_score": bollinger["score"],
       "volume_score": volume["score"],
       "weighted_score": weighted_score,
       "brains_agreeing": 3,
       "rsi_details": rsi,
       "macd_details": macd,
       "bollinger_details": bollinger,
       "volume_details": volume,
       "timestamp": current_time,
       "valid_for_minutes": 10,
       "description": "Strong buy signal - 3/4 indicators bullish"
   }

4. async scan_all_pairs(self) -> list
   - Loop through all 10 trading pairs
   - Call analyze_pair() for each
   - Collect all valid signals (non-None)
   - Sort by confidence (highest first)
   - Return list of signals

5. format_signal_message(self, signal: dict) -> str
   - Format signal into Telegram message:

   ⚡ SIGNAL ALERT

   🪙 Pair     : BTC/USDT
   📈 Direction : LONG
   💰 Entry    : $43,250.00
   🎯 Target 1 : $44,100.00
   🎯 Target 2 : $45,500.00
   🛑 Stop Loss: $42,800.00
   ⭐ Confidence: 78%
   ⏰ Valid for : 10 minutes

   📊 Brain Analysis:
   🧠 RSI      : 85/100 (Oversold bounce)
   🧠 MACD     : 72/100 (Bullish crossover)
   🧠 Bollinger: 80/100 (Lower band bounce)
   🧠 Volume   : 65/100 (Above average)

   ⏳ Next scan in 10 minutes

6. async run_continuous_scan(self, callback)
   - Run every 10 minutes (or configurable interval)
   - Call scan_all_pairs()
   - For each valid signal, call the callback function
   - The callback will handle sending to Telegram
   - Use asyncio.sleep between scans
   - Never stop running

IMPORTANT RULES:
- This is the HEART of the bot. Must be rock solid.
- Never send signal below 65% confidence
- Never send more than 1 signal per pair within 10 minutes
- Always log every analysis, even if signal not generated
- Log why a signal was rejected (confidence too low, cooldown, etc.)
- Round all prices to appropriate decimal places
  (BTC = 2 decimals, small coins = 4+ decimals)
- Handle errors gracefully - one pair failing shouldn't stop others