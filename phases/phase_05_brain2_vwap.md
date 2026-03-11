PROMPT FOR PHASE 5:
====================

Project: CryptoSignal Bot (continuing from Phase 1-4)
Task: Build MACD algorithm brain in algorithms/macd.py

CONTEXT: This is brain 2 of 4. Same structure as RSI brain.
Takes pandas DataFrame, returns analysis with score 0-100 
and direction (LONG/SHORT/NEUTRAL).

MACD settings from Config:
MACD_FAST = 12, MACD_SLOW = 26, MACD_SIGNAL = 9

BUILD algorithms/macd.py with these EXACT specifications:

CLASS: MACDAnalyzer

WHAT IS MACD (for algorithm accuracy):
- MACD = 12-period EMA minus 26-period EMA
- Signal Line = 9-period EMA of MACD
- Histogram = MACD minus Signal Line
- MACD crossing above Signal = BULLISH
- MACD crossing below Signal = BEARISH
- Histogram growing = momentum increasing
- Histogram shrinking = momentum decreasing

ADVANCED MACD ANALYSIS WE NEED:

1. Basic MACD Calculation (MACD line, Signal line, Histogram)
2. MACD Crossover Detection:
   - Bullish crossover: MACD crosses above Signal Line
   - Bearish crossover: MACD crosses below Signal Line
3. MACD Zero Line Cross:
   - MACD crossing above 0 = strong bullish
   - MACD crossing below 0 = strong bearish
4. Histogram Analysis:
   - Histogram increasing = momentum building
   - Histogram decreasing = momentum fading
   - Histogram flip (negative to positive) = trend change
5. MACD Divergence:
   - Price makes new high but MACD makes lower high = bearish
   - Price makes new low but MACD makes higher low = bullish

FUNCTIONS NEEDED:

1. __init__(self, fast=12, slow=26, signal=9)

2. calculate_ema(self, data, period)
   - Calculate Exponential Moving Average from scratch
   - Input: pandas Series, period
   - Return: EMA series

3. calculate_macd(self, df)
   - Calculate MACD line, Signal line, Histogram
   - Return: dict with all three as pandas Series
   - Calculate from scratch using calculate_ema

4. detect_crossover(self, macd_line, signal_line)
   - Check last 3 candles for crossover
   - Return: "BULLISH_CROSS", "BEARISH_CROSS", or "NONE"

5. detect_zero_cross(self, macd_line)
   - Check if MACD line crossed zero
   - Return: "BULLISH_ZERO_CROSS", "BEARISH_ZERO_CROSS", "NONE"

6. analyze_histogram(self, histogram)
   - Check histogram trend
   - Return: {
       "direction": "GROWING" / "SHRINKING",
       "momentum": "STRONG" / "WEAK" / "NEUTRAL",
       "flip": True/False (did it flip sign recently?)
     }

7. detect_divergence(self, df, macd_line, lookback=20)
   - Same logic as RSI divergence but with MACD
   - Return: {
       "bullish_divergence": True/False,
       "bearish_divergence": True/False
     }

8. analyze(self, df) ← MAIN FUNCTION
   - Run all analyses
   - Calculate score 0-100
   
   SCORING LOGIC (same structure as RSI):
   Base score = 50
   
   FOR LONG:
   + Bullish crossover: +15
   + Bullish zero cross: +10
   + Histogram growing positive: +10
   + Histogram flip to positive: +15
   + Bullish divergence: +20
   
   FOR SHORT:
   - Bearish crossover: -15
   - Bearish zero cross: -10
   - Histogram growing negative: -10
   - Histogram flip to negative: -15
   - Bearish divergence: -20
   
   RETURN FORMAT:
   {
     "brain": "MACD",
     "direction": "LONG" / "SHORT" / "NEUTRAL",
     "confidence": 0-100,
     "macd_value": current MACD value,
     "signal_value": current Signal value,
     "histogram_value": current Histogram value,
     "details": {
       "crossover": "BULLISH_CROSS" etc,
       "zero_cross": result,
       "histogram": histogram analysis dict,
       "divergence": True/False
     }
   }

REQUIREMENTS:
- Calculate ALL from scratch (no ta library)
- Same error handling standards as RSI brain
- Same return format structure
- Must be fast and efficient
- Handle edge cases (insufficient data, NaN, etc.)