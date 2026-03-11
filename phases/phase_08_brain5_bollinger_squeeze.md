PROMPT FOR PHASE 8:

PROJECT: CryptoSignal Bot (7-Brain System)
PHASE: 8 - Brain 5: Bollinger Bands + Squeeze Detection

Create file: algorithms/bollinger.py

WHAT ARE BOLLINGER BANDS:
Three lines creating a price envelope:
- Middle Band = 20-period SMA
- Upper Band = Middle + (2 × Standard Deviation)
- Lower Band = Middle - (2 × Standard Deviation)

WHAT IS BOLLINGER SQUEEZE:
When bands get VERY NARROW, it means volatility is extremely low.
Low volatility ALWAYS leads to HIGH volatility.
Squeeze = bands narrow → big price move is coming.
When bands expand after squeeze = trade in direction of breakout.

FORMULAS:
SMA = sum(closes[-20:]) / 20
StdDev = numpy.std(closes[-20:])
Upper = SMA + (2 × StdDev)
Lower = SMA - (2 × StdDev)

%B = (Price - Lower) / (Upper - Lower)
   %B > 1.0 = price ABOVE upper band
   %B < 0.0 = price BELOW lower band
   %B = 0.5 = price at middle band

Bandwidth = (Upper - Lower) / Middle × 100
   Low bandwidth = squeeze
   High bandwidth = volatile

CLASS: BollingerAnalyzer

PARAMETERS:
- period = 20
- std_dev = 2
- squeeze_threshold = 0.5 (bandwidth ratio for squeeze detection)

METHODS:

1. calculate_bands(self, closes: list) -> dict
   - Calculate for current candle AND previous candle
   - Return:
   {
       "upper": upper_band,
       "middle": middle_band,
       "lower": lower_band,
       "percent_b": percent_b,
       "bandwidth": bandwidth,
       "prev_percent_b": previous candle %B,
       "prev_bandwidth": previous candle bandwidth,
       "current_price": latest close
   }

2. get_signal(self, closes: list) -> dict

   SIGNAL LOGIC:

   STRONG BUY (score = 90-100):
   - Price BELOW Lower Band (%B <= 0.0)
   - AND %B is now rising (prev_%B < current_%B)
   - Price bouncing off lower band
   - OR: Squeeze release + price breaking ABOVE middle band

   BUY (score = 70-89):
   - %B between 0.0 and 0.2
   - Price near lower band, trending up
   - OR: Price touched lower band and bounced

   WEAK BUY (score = 55-69):
   - %B between 0.2 and 0.4
   - Price in lower half of bands

   NEUTRAL (score = 45-54):
   - %B between 0.4 and 0.6
   - Price near middle band

   WEAK SELL (score = 31-44):
   - %B between 0.6 and 0.8
   - Price in upper half

   SELL (score = 11-30):
   - %B between 0.8 and 1.0
   - Price near upper band, trending down

   STRONG SELL (score = 0-10):
   - Price ABOVE Upper Band (%B >= 1.0)
   - AND %B is falling
   - Price rejected from upper band
   - OR: Squeeze release + price breaking BELOW middle band

   SQUEEZE DETECTION (CRITICAL):
   - Calculate bandwidth for last 20 periods
   - Calculate average bandwidth
   - If current bandwidth < (average × squeeze_threshold):
     → SQUEEZE is active
   - If squeeze was active AND bandwidth now expanding:
     → SQUEEZE RELEASE
     → If price breaks above middle band → LONG boost (+10 to score)
     → If price breaks below middle band → SHORT boost (+10 to score)
     → This is a high-probability trade

   Return format:
   {
       "brain": "BOLLINGER",
       "upper_band": 44000,
       "middle_band": 43500,
       "lower_band": 43000,
       "percent_b": 0.15,
       "bandwidth": 2.3,
       "squeeze": True/False,
       "squeeze_releasing": True/False,
       "signal": "STRONG_BUY" / ... / "STRONG_SELL",
       "direction": "LONG" / "SHORT" / "NEUTRAL",
       "score": 0-100,
       "description": "Bollinger squeeze releasing upward"
   }

3. detect_squeeze(self, closes: list) -> dict
   Return:
   {
       "is_squeeze": True/False,
       "is_releasing": True/False,
       "release_direction": "UP" / "DOWN" / None,
       "squeeze_duration": number of candles in squeeze
   }

4. get_band_position(self, closes: list) -> str
   - "ABOVE_UPPER" / "UPPER_HALF" / "LOWER_HALF" / "BELOW_LOWER"

IMPORTANT:
- Use numpy for std deviation
- %B can be < 0 or > 1 (price outside bands)
- Squeeze detection is the UNIQUE VALUE of this brain
- Score must be 0-100
- Minimum 20 candles needed
WHEN YOU ADD THESE 3 BRAINS, UPDATE signal_engine.py:

OLD WEIGHTS (4 brains):
RSI:        25%
MACD:       25%  
Bollinger:  25%
Volume:     25%

NEW WEIGHTS (7 brains):
RSI:                15%
MACD:               15%
Bollinger:          15%
Volume:             15%
EMA Crossover:      15%  ← NEW
Support/Resistance: 15%  ← NEW
Candle Patterns:    10%  ← NEW (lower because it's 
                           often NEUTRAL)

UPDATED AGREEMENT BONUSES:
- 7/7 agree:  +20% confidence boost
- 6/7 agree:  +15% confidence boost
- 5/7 agree:  +10% confidence boost
- 4/7 agree:  +5% confidence boost
- 3/7 agree:  no bonus
- Below 3:    signal rejected

SPECIAL RULES:
- If EMA_CROSSOVER says trend is AGAINST signal direction:
  REDUCE confidence by 20% (trend is king)
- If SUPPORT_RESISTANCE confirms level: +10% boost
- If CANDLE_PATTERNS found strong pattern: +8% boost
- If VOLUME confirms: +10% boost
- If VOLUME contradicts: -15% penalty