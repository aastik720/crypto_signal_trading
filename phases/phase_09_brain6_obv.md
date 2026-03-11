PROMPT FOR PHASE 9:

PROJECT: CryptoSignal Bot (7-Brain System)
PHASE: 9 - Brain 6: OBV (On Balance Volume)

Create file: algorithms/obv.py

WHAT IS OBV:
OBV tracks CUMULATIVE buying and selling pressure by adding volume
on up days and subtracting volume on down days.
It reveals whether REAL money is flowing INTO or OUT OF an asset.

WHY OBV IS BETTER THAN SIMPLE VOLUME:
- Simple volume just shows how much was traded
- OBV shows the DIRECTION of volume flow
- OBV rising + price rising = CONFIRMED move (real)
- OBV falling + price rising = FAKE move (will reverse)
- OBV catches fake breakouts that volume analysis misses
- Professionals use OBV to detect institutional accumulation/distribution

OBV FORMULA:
If close > previous close: OBV = previous_OBV + current_volume
If close < previous close: OBV = previous_OBV - current_volume
If close == previous close: OBV = previous_OBV

OBV EMA: Apply EMA to OBV values for smoother signals
OBV Slope: Rate of change of OBV over N periods

CLASS: OBVAnalyzer

PARAMETERS:
- lookback = 20
- ema_period = 10 (for smoothed OBV)

METHODS:

1. calculate_obv(self, closes: list, volumes: list) -> list
   - Input: closes and volumes (same length)
   - Start with OBV = 0
   - For each candle:
     if close > prev_close: OBV += volume
     elif close < prev_close: OBV -= volume
     else: OBV unchanged
   - Return list of OBV values

2. calculate_obv_ema(self, obv_values: list) -> list
   - Apply 10-period EMA to OBV values
   - This smooths out noise
   - Return list of OBV-EMA values

3. get_signal(self, closes: list, volumes: list) -> dict
   - Calculate OBV
   - Calculate OBV-EMA
   - Detect OBV trend and price-OBV divergence

   OBV TREND:
   obv_slope = (obv[-1] - obv[-5]) / 5  (slope over 5 candles)
   price_slope = (closes[-1] - closes[-5]) / closes[-5] * 100

   SIGNAL LOGIC:

   STRONG BUY (score = 90-100):
   - OBV is rising strongly (OBV slope positive and steep)
   - AND price is also rising
   - AND OBV just crossed above its EMA
   - CONFIRMED buying pressure = institutions are buying
   - Score = 95

   BUY (score = 70-89):
   - OBV is above its EMA
   - AND OBV trend is upward
   - AND price confirms (also going up)
   - Healthy buying pressure
   - Score = 75

   WEAK BUY (score = 55-69):
   - OBV is near its EMA but slightly above
   - OR: BULLISH OBV DIVERGENCE detected:
     Price making LOWER lows but OBV making HIGHER lows
     → Smart money is secretly buying while price drops
     → This is a LEADING signal
   - Score = 60

   NEUTRAL (score = 45-54):
   - OBV is flat (slope near zero)
   - No clear direction
   - Score = 50

   WEAK SELL (score = 31-44):
   - OBV is near its EMA but slightly below
   - OR: BEARISH OBV DIVERGENCE detected:
     Price making HIGHER highs but OBV making LOWER highs
     → Smart money is secretly selling while price rises
     → FAKE rally, will reverse
   - Score = 40

   SELL (score = 11-30):
   - OBV is below its EMA
   - AND OBV trend is downward
   - AND price confirms (also going down)
   - Score = 25

   STRONG SELL (score = 0-10):
   - OBV is falling strongly
   - AND price is also falling
   - AND OBV just crossed below its EMA
   - CONFIRMED selling pressure = institutions are dumping
   - Score = 5

   VOLUME FLOW DETECTION:
   - ACCUMULATION: OBV rising while price is flat or slightly down
     → Big players buying quietly → Bullish (add 10 to score)
   - DISTRIBUTION: OBV falling while price is flat or slightly up
     → Big players selling quietly → Bearish (subtract 10 from score)

   Return format:
   {
       "brain": "OBV",
       "obv_current": 15000000,
       "obv_ema": 14500000,
       "obv_trend": "RISING" / "FALLING" / "FLAT",
       "obv_above_ema": True/False,
       "price_obv_confirmation": True/False,
       "divergence": "BULLISH" / "BEARISH" / None,
       "flow": "ACCUMULATION" / "DISTRIBUTION" / "NEUTRAL",
       "signal": "STRONG_BUY" / ... / "STRONG_SELL",
       "direction": "LONG" / "SHORT" / "NEUTRAL",
       "score": 0-100,
       "description": "OBV rising with price - confirmed buying"
   }

4. detect_obv_divergence(self, closes: list, obv_values: list) -> str
   - Compare last 10 candle swing points
   - BULLISH: price lower lows, OBV higher lows
   - BEARISH: price higher highs, OBV lower highs
   - Return "BULLISH" / "BEARISH" / None

5. detect_accumulation_distribution(self, closes: list, obv_values: list) -> str
   - Check if OBV is moving significantly while price is flat
   - Price flat = less than 0.2% change over 10 candles
   - OBV rising significantly while price flat = ACCUMULATION
   - OBV falling significantly while price flat = DISTRIBUTION
   - Return "ACCUMULATION" / "DISTRIBUTION" / "NEUTRAL"

IMPORTANT:
- OBV values can be very large numbers (millions)
- Always compare RELATIVE changes, not absolute values
- OBV divergence is the most valuable signal from this brain
- Use numpy for calculations
- Score must be 0-100
- Minimum 20 candles needed