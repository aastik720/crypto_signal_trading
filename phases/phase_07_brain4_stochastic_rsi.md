PROMPT FOR PHASE 7:
====================

Project: CryptoSignal Bot (continuing from Phase 1-6)
Task: Build Volume Analysis brain in algorithms/volume.py

CONTEXT: Brain 4 of 4. Volume is the CONFIRMATION brain.
It validates signals from other 3 brains. A signal without 
volume support is weak.

Settings: VOLUME_MA_PERIOD = 20 (from Config)

BUILD algorithms/volume.py with these EXACT specifications:

CLASS: VolumeAnalyzer

WHY VOLUME MATTERS:
- High volume + price up = STRONG bullish (real buying)
- High volume + price down = STRONG bearish (real selling)
- Low volume + price up = WEAK move (might reverse)
- Low volume + price down = WEAK move (might reverse)
- Volume spike = something big happening
- Volume drying up = trend exhaustion

ADVANCED VOLUME ANALYSIS:

1. Volume Moving Average (is current volume above/below avg?)
2. Volume Spike Detection (sudden volume increase)
3. On-Balance Volume (OBV) - running total of volume flow
4. Volume Price Trend (VPT) - volume weighted by price change
5. Volume Climax Detection - extreme volume at extreme prices
6. Accumulation/Distribution indicator
7. Volume Confirmation of Price Moves

FUNCTIONS NEEDED:

1. __init__(self, ma_period=20)

2. calculate_volume_ma(self, volume_series)
   - Simple moving average of volume
   - Return pandas Series

3. calculate_volume_ratio(self, current_volume, avg_volume)
   - Ratio of current to average volume
   - > 2.0 = volume spike
   - > 1.5 = above average
   - 0.8-1.2 = normal
   - < 0.5 = very low volume

4. calculate_obv(self, df)
   - On-Balance Volume from scratch:
     If close > previous close: OBV += volume
     If close < previous close: OBV -= volume
     If close == previous close: OBV unchanged
   - Return OBV series

5. detect_volume_spike(self, volume_series, threshold=2.0)
   - Is current volume more than 2x the average?
   - Return: True/False + spike_magnitude

6. detect_volume_trend(self, volume_series, periods=10)
   - Is volume trending up or down?
   - Return: "INCREASING", "DECREASING", "STABLE"

7. detect_volume_climax(self, df)
   - Extreme volume at price extremes
   - Often signals reversal
   - Return: "BUYING_CLIMAX", "SELLING_CLIMAX", "NONE"

8. calculate_accumulation_distribution(self, df)
   - A/D = ((Close - Low) - (High - Close)) / (High - Low) 
     × Volume
   - Return cumulative A/D series

9. volume_price_confirmation(self, df)
   - Check if volume confirms price direction
   - Price up + volume up = CONFIRMED
   - Price up + volume down = NOT CONFIRMED
   - Return: "CONFIRMED_BULLISH", "CONFIRMED_BEARISH", 
     "DIVERGENCE_BULLISH", "DIVERGENCE_BEARISH"

10. analyze(self, df) ← MAIN FUNCTION
    
    SCORING LOGIC:
    Base score = 50
    
    THIS BRAIN IS SPECIAL - it's a MULTIPLIER/CONFIRMATION:
    
    Volume above average + price rising: +15 (confirms long)
    Volume spike + price rising: +20
    OBV rising: +10
    Accumulation detected: +10
    Volume confirmed bullish: +15
    
    Volume above average + price falling: -15 (confirms short)
    Volume spike + price falling: -20
    OBV falling: -10
    Distribution detected: -10
    Volume confirmed bearish: -15
    
    Selling climax (potential reversal up): +10
    Buying climax (potential reversal down): -10
    
    Low volume (no confirmation): score stays near 50
    
    RETURN FORMAT:
    {
      "brain": "VOLUME",
      "direction": "LONG" / "SHORT" / "NEUTRAL",
      "confidence": 0-100,
      "current_volume": value,
      "avg_volume": value,
      "volume_ratio": value,
      "obv_trend": "RISING" / "FALLING",
      "details": {
        "spike": True/False,
        "trend": 