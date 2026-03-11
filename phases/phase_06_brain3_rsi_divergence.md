PROMPT FOR PHASE 6:
====================

Project: CryptoSignal Bot (continuing from Phase 1-5)
Task: Build Bollinger Bands brain in algorithms/bollinger.py

CONTEXT: Brain 3 of 4. Same structure as RSI and MACD brains.

Settings from Config:
BOLLINGER_PERIOD = 20, BOLLINGER_STD = 2

BUILD algorithms/bollinger.py with these EXACT specifications:

CLASS: BollingerAnalyzer

WHAT ARE BOLLINGER BANDS (for accuracy):
- Middle Band = 20-period Simple Moving Average (SMA)
- Upper Band = SMA + (2 × Standard Deviation)
- Lower Band = SMA - (2 × Standard Deviation)
- Price near Upper Band = potentially overbought
- Price near Lower Band = potentially oversold
- Band Squeeze = low volatility, breakout coming
- Band Expansion = high volatility

ADVANCED BOLLINGER ANALYSIS:

1. Basic Bollinger Calculation (Upper, Middle, Lower bands)
2. Price Position relative to bands:
   - Where is current price? Above upper? Below lower? Middle?
   - Calculate %B indicator: 
     %B = (Price - Lower) / (Upper - Lower)
     %B > 1 = above upper band
     %B < 0 = below lower band
3. Bandwidth Analysis:
   - Bandwidth = (Upper - Lower) / Middle × 100
   - Squeeze detection: bandwidth at 6-month low
   - Expansion detection: bandwidth increasing
4. Bollinger Bounce:
   - Price touches lower band and bounces = LONG
   - Price touches upper band and bounces = SHORT
5. Bollinger Breakout:
   - Price breaks above upper band with volume = LONG
   - Price breaks below lower band with volume = SHORT
6. Band Walking:
   - Price consistently touching upper band = strong uptrend
   - Price consistently touching lower band = strong downtrend

FUNCTIONS NEEDED:

1. __init__(self, period=20, std_dev=2)

2. calculate_bands(self, df)
   - Calculate SMA, Upper Band, Lower Band from scratch
   - Return dict with all three as pandas Series

3. calculate_percent_b(self, close, upper, lower)
   - Calculate %B indicator
   - Return pandas Series

4. calculate_bandwidth(self, upper, lower, middle)
   - Return bandwidth series

5. detect_squeeze(self, bandwidth, lookback=50)
   - Is current bandwidth in bottom 20% of recent range?
   - Return: True/False + squeeze_strength (0-100)

6. detect_bounce(self, df, upper, lower)
   - Did price touch a band and reverse?
   - Look at last 5 candles
   - Return: "BOUNCE_UPPER", "BOUNCE_LOWER", "NONE"

7. detect_breakout(self, df, upper, lower, volume_series)
   - Did price break through a band with above-average volume?
   - Return: "BREAKOUT_UP", "BREAKOUT_DOWN", "NONE"

8. detect_band_walk(self, df, upper, lower, periods=5)
   - Is price walking along a band?
   - Return: "WALKING_UPPER", "WALKING_LOWER", "NONE"

9. analyze(self, df) ← MAIN FUNCTION
   
   SCORING LOGIC:
   Base score = 50
   
   FOR LONG:
   + Price below lower band: +15
   + Bounce from lower band: +20
   + Squeeze detected (expect breakout): +10
   + %B below 0 (extreme oversold): +15
   + Breakout upward: +20
   
   FOR SHORT:
   - Price above upper band: -15
   - Bounce from upper band: -20
   - %B above 1 (extreme overbought): -15
   - Breakout downward: -20
   
   NEUTRAL ADJUSTMENTS:
   Band walking upper: depends on context (trend following)
   Band walking lower: depends on context
   
   RETURN FORMAT:
   {
     "brain": "BOLLINGER",
     "direction": "LONG" / "SHORT" / "NEUTRAL",
     "confidence": 0-100,
     "upper_band": value,
     "middle_band": value,
     "lower_band": value,
     "percent_b": value,
     "bandwidth": value,
     "details": {
       "squeeze": True/False,
       "bounce": result,
       "breakout": result,
       "band_walk": result
     }
   }

REQUIREMENTS:
- Calculate from scratch (no ta library)
- Same standards as RSI and MACD brains
- Handle all edge cases