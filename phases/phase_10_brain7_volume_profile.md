PROMPT FOR PHASE 10:

PROJECT: CryptoSignal Bot (7-Brain System)
PHASE: 10 - Brain 7: Volume Profile (Support/Resistance Zones)

Create file: algorithms/volume_profile.py

WHAT IS VOLUME PROFILE:
Volume Profile shows how much volume was traded at EACH PRICE LEVEL.
Unlike time-based volume (volume per candle), this shows volume per PRICE.
Zones with HIGH volume = strong support/resistance (price bounces here)
Zones with LOW volume = weak zones (price moves through quickly)

KEY CONCEPTS:
- POC (Point of Control): Price level with MOST volume traded
  → Strongest magnet for price, acts as support AND resistance
  → Price tends to return to POC
- HVN (High Volume Node): Price zone with high volume
  → Strong support/resistance, price consolidates here
- LVN (Low Volume Node): Price zone with low volume
  → Price moves through quickly, either up or down
- Value Area: Range where 70% of volume was traded
  → Price spends most time in value area

WHY VOLUME PROFILE:
- Shows WHERE smart money has positions
- Identifies invisible support/resistance lines
- Predicts where price will bounce or break
- Professional-grade analysis
- Most retail traders don't use this (your edge!)

HOW TO CALCULATE:
1. Take last 50 candles
2. Find price range: highest high to lowest low
3. Divide range into 20 bins (equal price intervals)
4. For each candle:
   - Determine which bin the close price falls into
   - Add that candle's volume to that bin
5. Result: volume distribution across price levels

CLASS: VolumeProfileAnalyzer

PARAMETERS:
- lookback = 50 (candles to analyze)
- num_bins = 20 (price level divisions)
- value_area_percent = 0.70 (70% of volume)

METHODS:

1. calculate_volume_profile(self, highs: list, lows: list,
                            closes: list, volumes: list) -> dict
   - Input: last 50 candles data
   - Find price range: max(highs) to min(lows)
   - Create 20 bins from low to high
   - For each candle, distribute volume to appropriate bin:
     - Simple method: assign all volume to the close price bin
     - Better method: distribute volume across high-low range
       (split volume equally between all bins the candle touched)
   - Find POC (bin with most volume)
   - Calculate Value Area (bins containing 70% of total volume,
     expanding outward from POC)
   
   Return:
   {
       "poc_price": 43250.00 (center of POC bin),
       "poc_volume": 15000 (volume at POC),
       "value_area_high": 43500.00 (top of value area),
       "value_area_low": 43000.00 (bottom of value area),
       "current_price": 43350.00,
       "price_vs_poc": "ABOVE" / "BELOW" / "AT_POC",
       "price_in_value_area": True/False,
       "nearest_hvn_above": 43600.00 (next resistance),
       "nearest_hvn_below": 43100.00 (next support),
       "nearest_lvn_above": 43450.00 (weak zone above),
       "nearest_lvn_below": 43150.00 (weak zone below),
       "bins": [(price_level, volume), ...]
   }

2. find_hvn_lvn(self, bins: list) -> dict
   - HVN: bins with volume > average_bin_volume * 1.5
   - LVN: bins with volume < average_bin_volume * 0.5
   - Return:
   {
       "hvn_levels": [43100, 43500, ...],  (support/resistance)
       "lvn_levels": [43300, 43700, ...]   (weak zones)
   }

3. get_signal(self, highs: list, lows: list,
              closes: list, volumes: list) -> dict

   SIGNAL LOGIC:

   STRONG BUY (score = 90-100):
   - Price at or below strong HVN (high volume support)
   - AND price showing signs of bouncing
   - AND price near Value Area Low
   - Price at major support = strong buy
   - Score = 92

   BUY (score = 70-89):
   - Price below POC but above nearest HVN support
   - AND moving toward POC (likely to reach it)
   - Price attracted toward POC
   - Score = 75

   WEAK BUY (score = 55-69):
   - Price below POC
   - In LVN zone (will move quickly toward next HVN)
   - Next HVN is above = will likely move up
   - Score = 60

   NEUTRAL (score = 45-54):
   - Price at or very near POC
   - Price in value area, consolidated
   - No clear direction from volume profile
   - Score = 50

   WEAK SELL (score = 31-44):
   - Price above POC
   - In LVN zone
   - Next HVN is below = might drop back
   - Score = 40

   SELL (score = 11-30):
   - Price above POC and approaching HVN resistance above
   - AND showing signs of rejection
   - Score = 25

   STRONG SELL (score = 0-10):
   - Price at or above strong HVN (high volume resistance)
   - AND price showing rejection
   - AND price near Value Area High
   - Price at major resistance = strong sell
   - Score = 8

   SMART LEVEL DETECTION:
   - Find nearest support (HVN below current price)
   - Find nearest resistance (HVN above current price)
   - These levels are used by signal_engine for:
     → Stop loss (just below support for LONG)
     → Target (next resistance for LONG)
     → Better levels than simple percentage-based ones

   Return format:
   {
       "brain": "VOLUME_PROFILE",
       "poc_price": 43250.00,
       "value_area_high": 43500.00,
       "value_area_low": 43000.00,
       "nearest_support": 43100.00 (nearest HVN below),
       "nearest_resistance": 43600.00 (nearest HVN above),
       "price_position": "ABOVE_POC" / "BELOW_POC" / "AT_POC",
       "in_value_area": True/False,
       "signal": "STRONG_BUY" / ... / "STRONG_SELL",
       "direction": "LONG" / "SHORT" / "NEUTRAL",
       "score": 0-100,
       "description": "Price at high volume support zone"
   }

IMPORTANT:
- This is the most computation-heavy brain
- Use numpy for bin calculations
- Price levels should be rounded appropriately
- For BTC: round to nearest $50
- For small coins: round to appropriate decimals
- POC is the most important output
- Score must be 0-100
- Minimum 50 candles needed
- The support/resistance levels from this brain are used
  by signal_engine for smarter stop loss and target calculations