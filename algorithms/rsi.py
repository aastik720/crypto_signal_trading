# ============================================
# CRYPTO SIGNAL BOT - RSI ANALYZER
# ============================================
# Brain #1 of 4: Relative Strength Index
#
# RSI measures the speed and magnitude of
# recent price changes to evaluate whether
# an asset is overbought or oversold.
#
# RSI ranges from 0 to 100:
#   < 20  → Extreme oversold (strong LONG)
#   < 30  → Oversold (LONG signal)
#   30-70 → Neutral zone
#   > 70  → Overbought (SHORT signal)
#   > 80  → Extreme overbought (strong SHORT)
#
# Advanced analysis includes:
#   - RSI divergence detection
#   - Centerline (50) crossover
#   - RSI trend direction
#   - Extreme level classification
#
# RSI is calculated FROM SCRATCH using Wilder's
# smoothing method — NO external library used.
# This gives us full control and understanding
# of the calculation.
#
# Usage:
#   from algorithms.rsi import rsi_analyzer
#   result = rsi_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class RSIAnalyzer:
    """
    RSI-based trading signal analyzer.

    Calculates RSI from raw price data, detects
    divergences, trends, and extreme levels, then
    produces a scored signal with direction and
    confidence percentage.

    Attributes:
        period (int):  RSI calculation period (default 14)
        results (dict): Stores latest analysis results
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self, period=None):
        """
        Initialize the RSI Analyzer.

        Args:
            period (int): RSI calculation period.
                         Uses Config.RSI_PERIOD if not provided.
                         Standard value is 14 periods.
        """
        # ------ RSI period from Config or argument ------
        # Config.RSI_PERIOD = 14 by default
        if period is not None:
            self.period = period
        else:
            self.period = Config.RSI_PERIOD

        # ------ Storage for latest analysis results ------
        # Updated every time analyze() is called
        self.results = {}

        print("[RSI] ✅ Analyzer initialized | Period: {}".format(
            self.period
        ))

    # ============================================
    # FUNCTION 2: CALCULATE RSI (From Scratch)
    # ============================================

    def calculate_rsi(self, df):
        """
        Calculates RSI using Wilder's Smoothing Method.

        This is the INDUSTRY STANDARD RSI formula:

        Step 1: Calculate price changes (deltas)
            delta[i] = close[i] - close[i-1]

        Step 2: Separate into gains and losses
            gain[i] = delta[i] if delta[i] > 0, else 0
            loss[i] = |delta[i]| if delta[i] < 0, else 0

        Step 3: First averages (Simple Moving Average)
            first_avg_gain = mean(gain[1 : period+1])
            first_avg_loss = mean(loss[1 : period+1])

        Step 4: Subsequent averages (Wilder's EMA)
            avg_gain[i] = (prev_avg_gain * (period-1) + gain[i]) / period
            avg_loss[i] = (prev_avg_loss * (period-1) + loss[i]) / period

        Step 5: Relative Strength and RSI
            RS = avg_gain / avg_loss
            RSI = 100 - (100 / (1 + RS))

        Special case: if avg_loss == 0 → RSI = 100
                      (all gains, no losses)

        Args:
            df (DataFrame): Must have 'close' column (float)

        Returns:
            pd.Series: RSI values (0-100) with same index as df.
                      First 'period' values are NaN (insufficient data).
                      Returns None on error.
        """
        try:
            # ------ Validate input ------
            if df is None or df.empty:
                print("[RSI] ⚠️ Empty DataFrame received")
                return None

            if "close" not in df.columns:
                print("[RSI] ⚠️ 'close' column missing from DataFrame")
                return None

            close = df["close"].astype(float).copy()

            # Need at least period + 1 prices for first RSI value
            min_required = self.period + 1
            if len(close) < min_required:
                print("[RSI] ⚠️ Need {} prices, got {}".format(
                    min_required, len(close)
                ))
                return None

            # ------ Step 1: Price changes ------
            # delta[0] = NaN (no previous price)
            # delta[i] = close[i] - close[i-1]
            delta = close.diff()

            # ------ Step 2: Separate gains and losses ------
            # Gains: keep positive deltas, zero out negatives
            gains = delta.copy()
            gains[gains < 0] = 0.0

            # Losses: keep absolute value of negative deltas
            losses = delta.copy()
            losses[losses > 0] = 0.0
            losses = losses.abs()

            # ------ Step 3: First averages (SMA of first 'period' values) ------
            # Use indices 1 through period (that's 'period' values)
            # Index 0 is NaN because diff() can't compute it
            first_avg_gain = gains.iloc[1:self.period + 1].mean()
            first_avg_loss = losses.iloc[1:self.period + 1].mean()

            # Handle edge case: all NaN in initial window
            if np.isnan(first_avg_gain):
                first_avg_gain = 0.0
            if np.isnan(first_avg_loss):
                first_avg_loss = 0.0

            # ------ Step 4: Build smoothed averages using Wilder's method ------
            # Pre-allocate arrays for speed
            data_length = len(close)
            avg_gain_arr = np.zeros(data_length, dtype=np.float64)
            avg_loss_arr = np.zeros(data_length, dtype=np.float64)

            # Set first calculated averages at index 'period'
            avg_gain_arr[self.period] = first_avg_gain
            avg_loss_arr[self.period] = first_avg_loss

            # Convert to numpy for faster iteration
            gains_np = gains.to_numpy()
            losses_np = losses.to_numpy()

            # Wilder's smoothing for subsequent values:
            # avg = (prev_avg * (period - 1) + current) / period
            for i in range(self.period + 1, data_length):
                avg_gain_arr[i] = (
                    (avg_gain_arr[i - 1] * (self.period - 1) + gains_np[i])
                    / self.period
                )
                avg_loss_arr[i] = (
                    (avg_loss_arr[i - 1] * (self.period - 1) + losses_np[i])
                    / self.period
                )

            # ------ Step 5: Calculate RSI ------
            # Initialize with NaN (invalid values for first 'period' entries)
            rsi_values = np.full(data_length, np.nan, dtype=np.float64)

            for i in range(self.period, data_length):
                if avg_loss_arr[i] == 0.0:
                    # No losses at all → RSI = 100 (maximum bullish)
                    rsi_values[i] = 100.0
                elif avg_gain_arr[i] == 0.0:
                    # No gains at all → RSI = 0 (maximum bearish)
                    rsi_values[i] = 0.0
                else:
                    rs = avg_gain_arr[i] / avg_loss_arr[i]
                    rsi_values[i] = 100.0 - (100.0 / (1.0 + rs))

            # ------ Build pandas Series with original index ------
            rsi_series = pd.Series(
                rsi_values,
                index=close.index,
                name="RSI",
                dtype=np.float64,
            )

            # Count valid (non-NaN) RSI values
            valid_count = rsi_series.dropna().shape[0]
            if valid_count > 0:
                current = rsi_series.dropna().iloc[-1]
                print("[RSI] Calculated | {} valid values | "
                      "Current RSI: {:.2f}".format(valid_count, current))

            return rsi_series

        except Exception as e:
            print("[RSI] ❌ RSI calculation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 3: DETECT DIVERGENCE
    # ============================================

    def detect_divergence(self, df, rsi_series, lookback=20):
        """
        Detects bullish and bearish RSI divergences.

        Divergence = price and RSI moving in opposite directions.
        This is one of the STRONGEST reversal indicators.

        BULLISH DIVERGENCE (reversal upward):
            Price makes a LOWER LOW  →  downtrend continuing
            RSI makes a HIGHER LOW  →  momentum weakening
            Interpretation: sellers losing power, price likely to reverse UP

        BEARISH DIVERGENCE (reversal downward):
            Price makes a HIGHER HIGH  →  uptrend continuing
            RSI makes a LOWER HIGH    →  momentum weakening
            Interpretation: buyers losing power, price likely to reverse DOWN

        Detection method:
        1. Look at the last 'lookback' candles
        2. Find swing lows (local minima) and swing highs (local maxima)
        3. Compare the two most recent swing points
        4. Check if price and RSI diverge

        Swing point detection:
            Low:  price[i] < price[i-1] AND price[i] <= price[i+1]
            High: price[i] > price[i-1] AND price[i] >= price[i+1]

        Strength calculation:
            Based on magnitude of divergence between price and RSI.
            Larger difference = stronger signal.

        Args:
            df (DataFrame):     Must have 'close' column
            rsi_series (Series): RSI values from calculate_rsi()
            lookback (int):     How many candles to check (default 20)

        Returns:
            dict: {
                "bullish_divergence": True/False,
                "bearish_divergence": True/False,
                "divergence_strength": 0-100
            }
        """
        # Default result for any failure or insufficient data
        default_result = {
            "bullish_divergence": False,
            "bearish_divergence": False,
            "divergence_strength": 0,
        }

        try:
            # ------ Validate inputs ------
            if df is None or df.empty:
                return default_result

            if rsi_series is None or rsi_series.empty:
                return default_result

            # ------ Extract last 'lookback' candles ------
            # Use min() to handle cases where data < lookback
            actual_lookback = min(lookback, len(df), len(rsi_series))

            if actual_lookback < 5:
                # Need at least 5 candles for swing detection
                return default_result

            price = df["close"].iloc[-actual_lookback:].values.astype(float)
            rsi = rsi_series.iloc[-actual_lookback:].values.astype(float)

            # ------ Remove positions with NaN RSI ------
            # Build a mask of valid (non-NaN) positions
            valid_mask = ~np.isnan(rsi)

            if valid_mask.sum() < 5:
                # Not enough valid RSI values for analysis
                return default_result

            # ------ Find swing lows (local minima) ------
            # A swing low at index i means:
            #   price[i] < price[i-1] AND price[i] <= price[i+1]
            # We skip first and last indices (need neighbors)
            swing_lows = []
            for i in range(1, len(price) - 1):
                if not valid_mask[i]:
                    continue
                if price[i] < price[i - 1] and price[i] <= price[i + 1]:
                    swing_lows.append(i)

            # ------ Find swing highs (local maxima) ------
            swing_highs = []
            for i in range(1, len(price) - 1):
                if not valid_mask[i]:
                    continue
                if price[i] > price[i - 1] and price[i] >= price[i + 1]:
                    swing_highs.append(i)

            bullish_div = False
            bearish_div = False
            div_strength = 0.0

            # ------ Check BULLISH divergence ------
            # Need at least 2 swing lows to compare
            if len(swing_lows) >= 2:
                # Use the two MOST RECENT swing lows
                older_idx = swing_lows[-2]
                newer_idx = swing_lows[-1]

                # Price: newer low is LOWER (lower low in price)
                price_lower_low = price[newer_idx] < price[older_idx]

                # RSI: newer low is HIGHER (higher low in RSI)
                rsi_higher_low = rsi[newer_idx] > rsi[older_idx]

                if price_lower_low and rsi_higher_low:
                    bullish_div = True

                    # Calculate strength based on divergence magnitude
                    # How much did price drop vs how much RSI rose?
                    price_diff_pct = abs(
                        price[older_idx] - price[newer_idx]
                    ) / price[older_idx] * 100.0

                    rsi_diff = abs(rsi[newer_idx] - rsi[older_idx])

                    # Weighted combination:
                    # - RSI diff * 3: a 10-point RSI div → 30 strength
                    # - Price diff * 10: a 2% price div → 20 strength
                    div_strength = min(
                        100.0,
                        rsi_diff * 3.0 + price_diff_pct * 10.0
                    )

                    print("[RSI] 🔍 BULLISH DIVERGENCE detected | "
                          "Price lower low: {:.2f}→{:.2f} | "
                          "RSI higher low: {:.1f}→{:.1f} | "
                          "Strength: {:.0f}".format(
                              price[older_idx], price[newer_idx],
                              rsi[older_idx], rsi[newer_idx],
                              div_strength
                          ))

            # ------ Check BEARISH divergence ------
            # Need at least 2 swing highs to compare
            if len(swing_highs) >= 2:
                older_idx = swing_highs[-2]
                newer_idx = swing_highs[-1]

                # Price: newer high is HIGHER (higher high in price)
                price_higher_high = price[newer_idx] > price[older_idx]

                # RSI: newer high is LOWER (lower high in RSI)
                rsi_lower_high = rsi[newer_idx] < rsi[older_idx]

                if price_higher_high and rsi_lower_high:
                    bearish_div = True

                    price_diff_pct = abs(
                        price[newer_idx] - price[older_idx]
                    ) / price[older_idx] * 100.0

                    rsi_diff = abs(rsi[older_idx] - rsi[newer_idx])

                    # Only overwrite strength if no bullish div found,
                    # or if bearish is stronger
                    new_strength = min(
                        100.0,
                        rsi_diff * 3.0 + price_diff_pct * 10.0
                    )

                    if new_strength > div_strength:
                        div_strength = new_strength

                    print("[RSI] 🔍 BEARISH DIVERGENCE detected | "
                          "Price higher high: {:.2f}→{:.2f} | "
                          "RSI lower high: {:.1f}→{:.1f} | "
                          "Strength: {:.0f}".format(
                              price[older_idx], price[newer_idx],
                              rsi[older_idx], rsi[newer_idx],
                              new_strength
                          ))

            return {
                "bullish_divergence": bullish_div,
                "bearish_divergence": bearish_div,
                "divergence_strength": round(div_strength, 2),
            }

        except Exception as e:
            print("[RSI] ❌ Divergence detection error: {}".format(e))
            return default_result

    # ============================================
    # FUNCTION 4: CHECK EXTREME LEVELS
    # ============================================

    def check_extreme_levels(self, current_rsi):
        """
        Classifies the current RSI value into a named level.

        Levels (checked from most extreme to least):
            < 20  → EXTREME_OVERSOLD  (very strong buy zone)
            < 30  → OVERSOLD          (buy zone)
            < 45  → NEUTRAL_BEARISH   (slight bearish lean)
            45-55 → NEUTRAL           (no clear signal)
            > 55  → NEUTRAL_BULLISH   (slight bullish lean)
            > 70  → OVERBOUGHT        (sell zone)
            > 80  → EXTREME_OVERBOUGHT (very strong sell zone)

        Args:
            current_rsi (float): Current RSI value (0-100)

        Returns:
            str: Level name string
        """
        try:
            # ------ Validate input ------
            if current_rsi is None or np.isnan(current_rsi):
                return "NEUTRAL"

            # ------ Classify from extreme to neutral ------
            # Check order matters: extremes first, then regular
            if current_rsi < 20:
                return "EXTREME_OVERSOLD"
            elif current_rsi < 30:
                return "OVERSOLD"
            elif current_rsi < 45:
                return "NEUTRAL_BEARISH"
            elif current_rsi <= 55:
                return "NEUTRAL"
            elif current_rsi <= 70:
                return "NEUTRAL_BULLISH"
            elif current_rsi <= 80:
                return "OVERBOUGHT"
            else:
                return "EXTREME_OVERBOUGHT"

        except Exception as e:
            print("[RSI] ❌ Level check error: {}".format(e))
            return "NEUTRAL"

    # ============================================
    # FUNCTION 5: CHECK CENTERLINE CROSS
    # ============================================

    def check_centerline_cross(self, rsi_series):
        """
        Detects RSI crossing the 50 centerline.

        The 50 level is the midpoint of RSI and acts as
        a momentum divider:
        - RSI crossing ABOVE 50 = bullish momentum shift
        - RSI crossing BELOW 50 = bearish momentum shift

        Checks the last 3 candles for a crossing event.
        If multiple crosses occurred, returns the most recent.

        Args:
            rsi_series (pd.Series): RSI values

        Returns:
            str: "BULLISH_CROSS" | "BEARISH_CROSS" | "NONE"
        """
        try:
            # ------ Validate input ------
            if rsi_series is None or rsi_series.empty:
                return "NONE"

            # ------ Get last 3 valid RSI values ------
            valid_rsi = rsi_series.dropna()

            if len(valid_rsi) < 2:
                return "NONE"

            # Take the last 3 (or fewer if not available)
            last_n = valid_rsi.iloc[-3:]

            # ------ Check from most recent to oldest ------
            # This ensures we catch the latest crossing event
            values = last_n.values

            for i in range(len(values) - 1, 0, -1):
                prev_val = values[i - 1]
                curr_val = values[i]

                # Skip if either value is NaN (extra safety)
                if np.isnan(prev_val) or np.isnan(curr_val):
                    continue

                # Crossed from below 50 to above 50 → bullish
                if prev_val < 50.0 and curr_val >= 50.0:
                    print("[RSI] ↗️ Centerline BULLISH cross detected "
                          "({:.1f} → {:.1f})".format(prev_val, curr_val))
                    return "BULLISH_CROSS"

                # Crossed from above 50 to below 50 → bearish
                if prev_val > 50.0 and curr_val <= 50.0:
                    print("[RSI] ↘️ Centerline BEARISH cross detected "
                          "({:.1f} → {:.1f})".format(prev_val, curr_val))
                    return "BEARISH_CROSS"

            return "NONE"

        except Exception as e:
            print("[RSI] ❌ Centerline cross check error: {}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 6: GET RSI TREND
    # ============================================

    def get_rsi_trend(self, rsi_series, periods=5):
        """
        Determines RSI direction over the last N candles.

        Combines TWO checks for reliability:
        1. Net change: RSI[now] - RSI[N candles ago]
        2. Consistency: what % of individual moves were
           in the same direction?

        A trend is confirmed when:
        - Net change > 2 RSI points AND
        - 60%+ of individual moves are in that direction

        This dual check prevents false signals from
        choppy/noisy RSI movement.

        Args:
            rsi_series (pd.Series): RSI values
            periods (int):         Lookback window (default 5)

        Returns:
            str: "RISING" | "FALLING" | "FLAT"
        """
        try:
            # ------ Validate input ------
            if rsi_series is None or rsi_series.empty:
                return "FLAT"

            valid_rsi = rsi_series.dropna()

            # Need at least 3 valid values for trend detection
            if len(valid_rsi) < 3:
                return "FLAT"

            # ------ Get last N values ------
            actual_periods = min(periods, len(valid_rsi))
            last_n = valid_rsi.iloc[-actual_periods:]

            # ------ Check 1: Net change ------
            net_change = last_n.iloc[-1] - last_n.iloc[0]

            # ------ Check 2: Direction consistency ------
            # Calculate individual candle-to-candle changes
            diffs = last_n.diff().dropna()

            if len(diffs) == 0:
                return "FLAT"

            rising_count = (diffs > 0).sum()
            falling_count = (diffs < 0).sum()
            total_moves = len(diffs)

            # Consistency threshold: 60% of moves in same direction
            consistency_threshold = 0.6

            # ------ Combine both checks ------
            # Net change > 2 RSI points AND mostly rising moves
            if (net_change > 2.0 and
                    rising_count >= total_moves * consistency_threshold):
                return "RISING"

            # Net change < -2 RSI points AND mostly falling moves
            if (net_change < -2.0 and
                    falling_count >= total_moves * consistency_threshold):
                return "FALLING"

            return "FLAT"

        except Exception as e:
            print("[RSI] ❌ Trend detection error: {}".format(e))
            return "FLAT"

    # ============================================
    # FUNCTION 7: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        MAIN ANALYSIS FUNCTION — Runs all RSI checks and produces
        a scored trading signal.

        Pipeline:
        1. Calculate RSI from close prices
        2. Classify current RSI level
        3. Detect divergences (bullish/bearish)
        4. Check RSI trend direction
        5. Check centerline (50) crossover
        6. Calculate composite score (0-100)
        7. Determine direction and confidence

        SCORING SYSTEM:
        Base score = 50 (neutral center)

        LONG factors (add to score):
        +25  RSI < 20  (extreme oversold)
        +15  RSI < 30  (oversold) — NOT added if < 20
        +20  Bullish divergence detected
        +10  RSI rising from oversold territory
        + 5  Centerline bullish cross

        SHORT factors (subtract from score):
        -25  RSI > 80  (extreme overbought)
        -15  RSI > 70  (overbought) — NOT subtracted if > 80
        -20  Bearish divergence detected
        -10  RSI falling from overbought territory
        - 5  Centerline bearish cross

        Score clamped to 0-100 range.

        DIRECTION MAPPING:
         0-30  → Strong SHORT  | confidence = (50-score) * 2
        30-45  → Weak SHORT    | confidence = (50-score) * 2
        45-55  → NEUTRAL       | confidence = 0
        55-70  → Weak LONG     | confidence = (score-50) * 2
        70-100 → Strong LONG   | confidence = (score-50) * 2

        Args:
            df (DataFrame): Price data with columns:
                           [open, high, low, close, volume]
                           All float type.

        Returns:
            dict: {
                "brain": "RSI",
                "direction": "LONG" / "SHORT" / "NEUTRAL",
                "confidence": 0-100 (float),
                "rsi_value": current RSI (float),
                "details": {
                    "level": str,
                    "divergence": bool,
                    "trend": str,
                    "centerline": str
                }
            }
            Returns neutral result on any error.
        """
        # ------ Default neutral result (returned on errors) ------
        neutral_result = {
            "brain": "RSI",
            "direction": "NEUTRAL",
            "confidence": 0,
            "rsi_value": 50.0,
            "details": {
                "level": "NEUTRAL",
                "divergence": False,
                "trend": "FLAT",
                "centerline": "NONE",
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input DataFrame
            # ============================================
            if df is None or df.empty:
                print("[RSI] ⚠️ No data provided for analysis")
                return neutral_result

            if "close" not in df.columns:
                print("[RSI] ⚠️ 'close' column missing")
                return neutral_result

            if len(df) < self.period + 1:
                print("[RSI] ⚠️ Need {} rows, got {}".format(
                    self.period + 1, len(df)
                ))
                return neutral_result

            # ============================================
            # STEP 2: Calculate RSI
            # ============================================
            rsi_series = self.calculate_rsi(df)

            if rsi_series is None:
                print("[RSI] ⚠️ RSI calculation returned None")
                return neutral_result

            # Get current RSI value (latest valid value)
            valid_rsi = rsi_series.dropna()

            if len(valid_rsi) == 0:
                print("[RSI] ⚠️ No valid RSI values computed")
                return neutral_result

            current_rsi = float(valid_rsi.iloc[-1])

            # ============================================
            # STEP 3: Run all sub-analyses
            # ============================================

            # 3a: Classify RSI level
            level = self.check_extreme_levels(current_rsi)

            # 3b: Detect divergences
            divergence = self.detect_divergence(df, rsi_series, lookback=20)
            has_bullish_div = divergence["bullish_divergence"]
            has_bearish_div = divergence["bearish_divergence"]

            # 3c: Check RSI trend
            trend = self.get_rsi_trend(rsi_series, periods=5)

            # 3d: Check centerline crossover
            centerline = self.check_centerline_cross(rsi_series)

            # 3e: Check recent RSI history for oversold/overbought context
            # Used for "trending from oversold/overbought" scoring
            recent_window = min(5, len(valid_rsi))
            recent_rsi = valid_rsi.iloc[-recent_window:]
            was_recently_oversold = bool((recent_rsi < 30).any())
            was_recently_overbought = bool((recent_rsi > 70).any())

            # ============================================
            # STEP 4: Calculate composite score
            # ============================================
            score = 50.0  # Start at neutral center

            # ------ LONG factors (add to score) ------

            # RSI extreme oversold (< 20): +25 points
            if current_rsi < 20:
                score += 25.0
                print("[RSI] 📈 +25 pts | EXTREME OVERSOLD ({:.1f})".format(
                    current_rsi
                ))

            # RSI oversold (< 30 but >= 20): +15 points
            elif current_rsi < 30:
                score += 15.0
                print("[RSI] 📈 +15 pts | OVERSOLD ({:.1f})".format(
                    current_rsi
                ))

            # Bullish divergence: +20 points
            if has_bullish_div:
                score += 20.0
                print("[RSI] 📈 +20 pts | BULLISH DIVERGENCE")

            # RSI rising from oversold territory: +10 points
            # Condition: trend is RISING AND was recently oversold
            if (trend == "RISING" and
                    (current_rsi < 40 or was_recently_oversold)):
                score += 10.0
                print("[RSI] 📈 +10 pts | RISING from oversold zone")

            # Centerline bullish cross: +5 points
            if centerline == "BULLISH_CROSS":
                score += 5.0
                print("[RSI] 📈 + 5 pts | BULLISH centerline cross")

            # ------ SHORT factors (subtract from score) ------

            # RSI extreme overbought (> 80): -25 points
            if current_rsi > 80:
                score -= 25.0
                print("[RSI] 📉 -25 pts | EXTREME OVERBOUGHT ({:.1f})".format(
                    current_rsi
                ))

            # RSI overbought (> 70 but <= 80): -15 points
            elif current_rsi > 70:
                score -= 15.0
                print("[RSI] 📉 -15 pts | OVERBOUGHT ({:.1f})".format(
                    current_rsi
                ))

            # Bearish divergence: -20 points
            if has_bearish_div:
                score -= 20.0
                print("[RSI] 📉 -20 pts | BEARISH DIVERGENCE")

            # RSI falling from overbought territory: -10 points
            if (trend == "FALLING" and
                    (current_rsi > 60 or was_recently_overbought)):
                score -= 10.0
                print("[RSI] 📉 -10 pts | FALLING from overbought zone")

            # Centerline bearish cross: -5 points
            if centerline == "BEARISH_CROSS":
                score -= 5.0
                print("[RSI] 📉 - 5 pts | BEARISH centerline cross")

            # ============================================
            # STEP 5: Clamp score to 0-100 range
            # ============================================
            score = max(0.0, min(100.0, score))

            # ============================================
            # STEP 6: Determine direction and confidence
            # ============================================

            if score < 30:
                # Strong SHORT signal
                direction = "SHORT"
                confidence = (50.0 - score) * 2.0

            elif score < 45:
                # Weak SHORT signal
                direction = "SHORT"
                confidence = (50.0 - score) * 2.0

            elif score <= 55:
                # Neutral zone — no clear signal
                direction = "NEUTRAL"
                confidence = 0.0

            elif score <= 70:
                # Weak LONG signal
                direction = "LONG"
                confidence = (score - 50.0) * 2.0

            else:
                # Strong LONG signal
                direction = "LONG"
                confidence = (score - 50.0) * 2.0

            # Clamp confidence to 0-100
            confidence = max(0.0, min(100.0, round(confidence, 2)))

            # Track whether any divergence contributed to the signal
            divergence_relevant = (
                (has_bullish_div and direction in ("LONG", "NEUTRAL")) or
                (has_bearish_div and direction in ("SHORT", "NEUTRAL")) or
                (has_bullish_div or has_bearish_div)
            )

            # ============================================
            # STEP 7: Build result dictionary
            # ============================================
            result = {
                "brain": "RSI",
                "direction": direction,
                "confidence": confidence,
                "rsi_value": round(current_rsi, 2),
                "details": {
                    "level": level,
                    "divergence": divergence_relevant,
                    "trend": trend,
                    "centerline": centerline,
                },
            }

            # Store result for later reference
            self.results = result

            # ============================================
            # STEP 8: Log the analysis summary
            # ============================================
            print("\n[RSI] ═══════════════════════════════════")
            print("[RSI]  RSI Analysis Complete")
            print("[RSI]  RSI Value    : {:.2f}".format(current_rsi))
            print("[RSI]  Level        : {}".format(level))
            print("[RSI]  Trend        : {}".format(trend))
            print("[RSI]  Centerline   : {}".format(centerline))
            print("[RSI]  Divergence   : {}".format(
                "YES" if divergence_relevant else "No"
            ))
            print("[RSI]  Raw Score    : {:.1f}/100".format(score))
            print("[RSI]  Direction    : {}".format(direction))
            print("[RSI]  Confidence   : {:.1f}%".format(confidence))
            print("[RSI] ═══════════════════════════════════\n")

            return result

        except Exception as e:
            print("[RSI] ❌ Analysis error: {}".format(e))
            return neutral_result


# ==================================================
# MODULE-LEVEL SINGLETON INSTANCE
# ==================================================
# Every module imports this same instance:
#
#   from algorithms.rsi import rsi_analyzer
#   result = rsi_analyzer.analyze(dataframe)
#
# result = {
#     "brain": "RSI",
#     "direction": "LONG" / "SHORT" / "NEUTRAL",
#     "confidence": 0-100,
#     "rsi_value": float,
#     "details": {...}
# }
# ==================================================

rsi_analyzer = RSIAnalyzer()

print("[RSI] ✅ RSI module loaded and ready")