PROMPT FOR PHASE 4:
====================

Project: CryptoSignal Bot (continuing from Phase 1-3)
Task: Build RSI algorithm brain in algorithms/rsi.py

CONTEXT: This is one of 4 "brains" that analyze crypto data. 
Each brain gives a score from 0 to 100 indicating signal 
strength and direction (LONG or SHORT).

The data comes as pandas DataFrame with columns:
[timestamp, open, high, low, close, volume] - all float type.
RSI_PERIOD = 14 (from Config settings)

BUILD algorithms/rsi.py with these EXACT specifications:

CLASS: RSIAnalyzer

WHAT IS RSI (for algorithm accuracy):
- RSI measures speed and magnitude of price changes
- RSI ranges from 0 to 100
- RSI below 30 = OVERSOLD (potential LONG/BUY signal)
- RSI above 70 = OVERBOUGHT (potential SHORT/SELL signal)
- RSI between 30-70 = NEUTRAL zone

ADVANCED RSI ANALYSIS WE NEED:

1. Basic RSI Value (standard calculation)
2. RSI Divergence Detection:
   - Bullish Divergence: Price makes LOWER LOW but RSI makes 
     HIGHER LOW → Strong LONG signal
   - Bearish Divergence: Price makes HIGHER HIGH but RSI makes 
     LOWER HIGH → Strong SHORT signal
3. RSI Trend Analysis:
   - Is RSI trending up or down over last 5 candles?
4. RSI Extreme Levels:
   - RSI below 20 = EXTREME oversold (very strong LONG)
   - RSI above 80 = EXTREME overbought (very strong SHORT)
5. RSI Centerline Crossover:
   - RSI crossing above 50 = bullish momentum
   - RSI crossing below 50 = bearish momentum

FUNCTIONS NEEDED:

1. __init__(self, period=14)
   - Set RSI period
   - Initialize result storage

2. calculate_rsi(self, df)
   - Input: pandas DataFrame with 'close' column
   - Calculate RSI using standard formula:
     * Calculate price changes (delta)
     * Separate gains and losses
     * Calculate average gain and average loss (EMA method)
     * RS = avg_gain / avg_loss
     * RSI = 100 - (100 / (1 + RS))
   - Return RSI series (pandas Series)
   - DO NOT use any library for calculation, write from scratch
     (this ensures we understand exactly what's happening)

3. detect_divergence(self, df, rsi_series, lookback=20)
   - Check last 'lookback' candles for divergence
   - Find recent swing lows and swing highs in both price 
     and RSI
   - Return: {
       "bullish_divergence": True/False,
       "bearish_divergence": True/False,
       "divergence_strength": 0-100
     }

4. check_extreme_levels(self, current_rsi)
   - Return classification:
     * "EXTREME_OVERSOLD" if RSI < 20
     * "OVERSOLD" if RSI < 30
     * "NEUTRAL_BEARISH" if RSI 30-45
     * "NEUTRAL" if RSI 45-55
     * "NEUTRAL_BULLISH" if RSI 55-70
     * "OVERBOUGHT" if RSI > 70
     * "EXTREME_OVERBOUGHT" if RSI > 80

5. check_centerline_cross(self, rsi_series)
   - Check if RSI just crossed above or below 50
   - Look at last 3 candles
   - Return: "BULLISH_CROSS", "BEARISH_CROSS", or "NONE"

6. get_rsi_trend(self, rsi_series, periods=5)
   - Check RSI direction over last 'periods' candles
   - Return: "RISING", "FALLING", or "FLAT"

7. analyze(self, df) ← THIS IS THE MAIN FUNCTION
   - Takes the full DataFrame
   - Runs ALL above analyses
   - Calculates a SCORE from 0-100
   - Determines DIRECTION: "LONG", "SHORT", or "NEUTRAL"
   
   SCORING LOGIC:
   Base score starts at 50 (neutral)
   
   FOR LONG SIGNALS (add to score):
   + RSI below 30: +15 points
   + RSI below 20: +25 points (instead of 15)
   + Bullish divergence: +20 points
   + RSI trending up from oversold: +10 points
   + Centerline bullish cross: +5 points
   
   FOR SHORT SIGNALS (subtract from score):
   - RSI above 70: -15 points
   - RSI above 80: -25 points (instead of 15)
   - Bearish divergence: -20 points
   - RSI trending down from overbought: -10 points
   - Centerline bearish cross: -5 points
   
   Final score mapping:
   - Score 0-30: Strong SHORT signal, confidence = (50-score)*2
   - Score 30-45: Weak SHORT signal, confidence = (50-score)*2
   - Score 45-55: NEUTRAL, confidence = 0
   - Score 55-70: Weak LONG signal, confidence = (score-50)*2
   - Score 70-100: Strong LONG signal, confidence = (score-50)*2
   
   RETURN FORMAT:
   {
     "brain": "RSI",
     "direction": "LONG" / "SHORT" / "NEUTRAL",
     "confidence": 0-100,
     "rsi_value": current RSI value,
     "details": {
       "level": "OVERSOLD" etc,
       "divergence": True/False,
       "trend": "RISING" etc,
       "centerline": "BULLISH_CROSS" etc
     }
   }

REQUIREMENTS:
- Pure Python + pandas + numpy (NO ta library for RSI)
- Calculate RSI from scratch for full control
- All functions must handle edge cases (not enough data, 
  NaN values, etc.)
- Every function must have error handling
- Every function must have docstring
- Log important findings (like divergence detected)
- Must be fast - this runs every 10 minutes for 10 pairs