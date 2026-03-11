# ============================================
# CRYPTO SIGNAL BOT - MACD ANALYZER
# ============================================
# Brain #2 of 4: Moving Average Convergence
#                Divergence (MACD)
#
# MACD measures trend direction, momentum,
# and potential reversal points using the
# relationship between two EMAs.
#
# Components:
#   MACD Line    = EMA(12) - EMA(26)
#   Signal Line  = EMA(9) of MACD Line
#   Histogram    = MACD Line - Signal Line
#
# Key signals:
#   MACD > Signal → Bullish momentum
#   MACD < Signal → Bearish momentum
#   MACD > 0      → Price above long-term average
#   MACD < 0      → Price below long-term average
#   Histogram growing  → Momentum increasing
#   Histogram shrinking → Momentum fading
#
# All calculations done FROM SCRATCH.
# No external TA library used.
#
# Usage:
#   from algorithms.macd import macd_analyzer
#   result = macd_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class MACDAnalyzer:
    """
    MACD-based trading signal analyzer.

    Calculates MACD, Signal, and Histogram from raw
    price data, detects crossovers, zero-line crosses,
    histogram momentum shifts, and divergences. Then
    produces a scored signal with direction and confidence.

    Attributes:
        fast_period (int):   Fast EMA period (default 12)
        slow_period (int):   Slow EMA period (default 26)
        signal_period (int): Signal EMA period (default 9)
        results (dict):      Stores latest analysis results
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self, fast=None, slow=None, signal_period=None):
        """
        Initialize the MACD Analyzer.

        Args:
            fast (int):          Fast EMA period.
                                Uses Config.MACD_FAST if not given.
            slow (int):          Slow EMA period.
                                Uses Config.MACD_SLOW if not given.
            signal_period (int): Signal line EMA period.
                                Uses Config.MACD_SIGNAL if not given.
        """
        # ------ Periods from Config or arguments ------
        self.fast_period = fast if fast is not None else Config.MACD_FAST
        self.slow_period = slow if slow is not None else Config.MACD_SLOW
        self.signal_period = (
            signal_period if signal_period is not None else Config.MACD_SIGNAL
        )

        # ------ Minimum data needed for valid MACD ------
        # Slow EMA needs 'slow_period' candles for first value.
        # Signal EMA then needs 'signal_period' more candles.
        # Total = slow + signal - 1 (overlapping first value).
        # We add a small buffer for reliable analysis.
        self.min_data_points = self.slow_period + self.signal_period + 5

        # ------ Storage for latest analysis results ------
        self.results = {}

        print("[MACD] ✅ Analyzer initialized | "
              "Fast: {} | Slow: {} | Signal: {}".format(
                  self.fast_period, self.slow_period, self.signal_period
              ))

    # ============================================
    # FUNCTION 2: CALCULATE EMA (From Scratch)
    # ============================================

    def calculate_ema(self, data, period):
        """
        Calculates Exponential Moving Average from scratch.

        EMA gives more weight to recent prices, making it
        more responsive to new information than SMA.

        Formula:
            multiplier = 2 / (period + 1)
            EMA[period-1] = SMA of first 'period' values
            EMA[i] = (value[i] - EMA[i-1]) * multiplier + EMA[i-1]

        The multiplier determines how much weight the
        latest price gets:
        - Period 12 → multiplier = 0.1538 (15.38%)
        - Period 26 → multiplier = 0.0741 (7.41%)
        - Period 9  → multiplier = 0.2000 (20.00%)

        Args:
            data (pd.Series): Price data (or any numeric series)
            period (int):     EMA period

        Returns:
            pd.Series: EMA values with same index as input.
                      First (period-1) values are NaN.
                      Returns None on error.
        """
        try:
            # ------ Validate inputs ------
            if data is None or len(data) == 0:
                print("[MACD] ⚠️ Empty data for EMA calculation")
                return None

            if period <= 0:
                print("[MACD] ⚠️ Invalid EMA period: {}".format(period))
                return None

            if len(data) < period:
                print("[MACD] ⚠️ Need {} data points for EMA({}), "
                      "got {}".format(period, period, len(data)))
                return None

            # ------ Convert to numpy for speed ------
            values = data.astype(float).values
            data_length = len(values)

            # ------ EMA smoothing multiplier ------
            # Standard formula: 2 / (period + 1)
            multiplier = 2.0 / (period + 1.0)

            # ------ Pre-allocate result array with NaN ------
            ema_values = np.full(data_length, np.nan, dtype=np.float64)

            # ------ Seed: SMA of first 'period' values ------
            # This is the standard way to initialize EMA.
            # Using only non-NaN values in the initial window.
            initial_window = values[:period]
            valid_initial = initial_window[~np.isnan(initial_window)]

            if len(valid_initial) == 0:
                print("[MACD] ⚠️ All NaN in initial EMA window")
                return None

            ema_values[period - 1] = np.mean(valid_initial)

            # ------ Compute EMA recursively ------
            # EMA[i] = (value[i] - EMA[i-1]) * multiplier + EMA[i-1]
            # This is equivalent to:
            # EMA[i] = value[i] * multiplier + EMA[i-1] * (1 - multiplier)
            for i in range(period, data_length):
                current_val = values[i]

                # Skip NaN values — carry forward previous EMA
                if np.isnan(current_val):
                    ema_values[i] = ema_values[i - 1]
                else:
                    ema_values[i] = (
                        (current_val - ema_values[i - 1]) * multiplier
                        + ema_values[i - 1]
                    )

            # ------ Build pandas Series with original index ------
            ema_series = pd.Series(
                ema_values,
                index=data.index,
                name="EMA_{}".format(period),
                dtype=np.float64,
            )

            return ema_series

        except Exception as e:
            print("[MACD] ❌ EMA({}) calculation error: {}".format(period, e))
            return None

    # ============================================
    # FUNCTION 3: CALCULATE MACD
    # ============================================

    def calculate_macd(self, df):
        """
        Calculates all three MACD components from close prices.

        Components:
        1. MACD Line = EMA(fast) - EMA(slow)
           When fast EMA > slow EMA → MACD positive → bullish
           When fast EMA < slow EMA → MACD negative → bearish

        2. Signal Line = EMA(signal_period) of MACD Line
           Smoothed version of MACD for crossover detection

        3. Histogram = MACD Line - Signal Line
           Visual representation of gap between MACD and Signal
           Positive histogram → MACD above Signal → bullish
           Negative histogram → MACD below Signal → bearish

        Args:
            df (DataFrame): Must have 'close' column (float)

        Returns:
            dict: {
                "macd_line": pd.Series,
                "signal_line": pd.Series,
                "histogram": pd.Series
            }
            Returns None on error.
        """
        try:
            # ------ Validate input ------
            if df is None or df.empty:
                print("[MACD] ⚠️ Empty DataFrame received")
                return None

            if "close" not in df.columns:
                print("[MACD] ⚠️ 'close' column missing")
                return None

            close = df["close"].astype(float)

            if len(close) < self.min_data_points:
                print("[MACD] ⚠️ Need {} prices, got {}".format(
                    self.min_data_points, len(close)
                ))
                return None

            # ------ Step 1: Calculate fast and slow EMAs ------
            ema_fast = self.calculate_ema(close, self.fast_period)
            ema_slow = self.calculate_ema(close, self.slow_period)

            if ema_fast is None or ema_slow is None:
                print("[MACD] ⚠️ EMA calculation failed")
                return None

            # ------ Step 2: MACD Line = Fast EMA - Slow EMA ------
            macd_line = ema_fast - ema_slow
            macd_line.name = "MACD"

            # ------ Step 3: Signal Line = EMA of MACD Line ------
            # We need the valid (non-NaN) portion of MACD for this.
            # Create a clean series from first valid MACD value onward.
            first_valid_idx = macd_line.first_valid_index()

            if first_valid_idx is None:
                print("[MACD] ⚠️ No valid MACD values computed")
                return None

            # Get position-based index of first valid value
            first_valid_pos = macd_line.index.get_loc(first_valid_idx)
            macd_valid = macd_line.iloc[first_valid_pos:]

            if len(macd_valid) < self.signal_period:
                print("[MACD] ⚠️ Not enough MACD values for "
                      "Signal line ({} < {})".format(
                          len(macd_valid), self.signal_period
                      ))
                return None

            signal_line_partial = self.calculate_ema(
                macd_valid, self.signal_period
            )

            if signal_line_partial is None:
                print("[MACD] ⚠️ Signal line calculation failed")
                return None

            # Reindex signal line to match full DataFrame index
            signal_line = pd.Series(
                np.nan,
                index=df.index,
                name="Signal",
                dtype=np.float64,
            )
            signal_line.loc[signal_line_partial.index] = signal_line_partial

            # ------ Step 4: Histogram = MACD - Signal ------
            histogram = macd_line - signal_line
            histogram.name = "Histogram"

            # ------ Count valid values ------
            valid_hist = histogram.dropna()

            if len(valid_hist) > 0:
                print("[MACD] Calculated | {} valid points | "
                      "MACD: {:.6f} | Signal: {:.6f} | "
                      "Hist: {:.6f}".format(
                          len(valid_hist),
                          macd_line.dropna().iloc[-1],
                          signal_line.dropna().iloc[-1],
                          histogram.dropna().iloc[-1],
                      ))

            return {
                "macd_line": macd_line,
                "signal_line": signal_line,
                "histogram": histogram,
            }

        except Exception as e:
            print("[MACD] ❌ MACD calculation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 4: DETECT CROSSOVER
    # ============================================

    def detect_crossover(self, macd_line, signal_line):
        """
        Detects MACD/Signal line crossover in last 3 candles.

        BULLISH CROSSOVER:
            MACD was BELOW Signal → now ABOVE Signal
            Means: short-term momentum turning positive
            Interpretation: potential BUY signal

        BEARISH CROSSOVER:
            MACD was ABOVE Signal → now BELOW Signal
            Means: short-term momentum turning negative
            Interpretation: potential SELL signal

        Checks the 3 most recent candles to catch crossovers
        that happened 1-2 candles ago (still relevant).
        Returns the MOST RECENT crossover found.

        Args:
            macd_line (pd.Series):   MACD line values
            signal_line (pd.Series): Signal line values

        Returns:
            str: "BULLISH_CROSS" | "BEARISH_CROSS" | "NONE"
        """
        try:
            # ------ Validate inputs ------
            if macd_line is None or signal_line is None:
                return "NONE"

            # ------ Get last 3 valid pairs ------
            # Build difference: MACD - Signal
            # Positive = MACD above Signal, Negative = below
            diff = macd_line - signal_line

            # Drop NaN values and get last entries
            valid_diff = diff.dropna()

            if len(valid_diff) < 2:
                return "NONE"

            # Take last 3 (or fewer)
            check_count = min(3, len(valid_diff))
            recent = valid_diff.iloc[-check_count:]
            values = recent.values

            # ------ Scan from most recent to oldest ------
            for i in range(len(values) - 1, 0, -1):
                prev = values[i - 1]
                curr = values[i]

                # Skip NaN (extra safety)
                if np.isnan(prev) or np.isnan(curr):
                    continue

                # Previous: MACD below Signal → Current: MACD above Signal
                if prev < 0 and curr >= 0:
                    print("[MACD] ↗️ BULLISH crossover detected "
                          "(diff: {:.6f} → {:.6f})".format(prev, curr))
                    return "BULLISH_CROSS"

                # Previous: MACD above Signal → Current: MACD below Signal
                if prev > 0 and curr <= 0:
                    print("[MACD] ↘️ BEARISH crossover detected "
                          "(diff: {:.6f} → {:.6f})".format(prev, curr))
                    return "BEARISH_CROSS"

            return "NONE"

        except Exception as e:
            print("[MACD] ❌ Crossover detection error: {}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 5: DETECT ZERO LINE CROSS
    # ============================================

    def detect_zero_cross(self, macd_line):
        """
        Detects MACD line crossing the zero line.

        The zero line represents the point where the fast
        and slow EMAs are equal. Crossing it is significant:

        BULLISH ZERO CROSS:
            MACD goes from negative to positive
            Means: fast EMA now ABOVE slow EMA
            Interpretation: trend shifting bullish

        BEARISH ZERO CROSS:
            MACD goes from positive to negative
            Means: fast EMA now BELOW slow EMA
            Interpretation: trend shifting bearish

        Zero-line crosses are STRONGER signals than
        MACD/Signal crossovers because they confirm
        the actual trend direction, not just momentum.

        Checks last 3 candles for the crossing event.

        Args:
            macd_line (pd.Series): MACD line values

        Returns:
            str: "BULLISH_ZERO_CROSS" | "BEARISH_ZERO_CROSS" | "NONE"
        """
        try:
            # ------ Validate input ------
            if macd_line is None:
                return "NONE"

            valid_macd = macd_line.dropna()

            if len(valid_macd) < 2:
                return "NONE"

            # ------ Check last 3 candles ------
            check_count = min(3, len(valid_macd))
            recent = valid_macd.iloc[-check_count:]
            values = recent.values

            # Scan from most recent to oldest
            for i in range(len(values) - 1, 0, -1):
                prev = values[i - 1]
                curr = values[i]

                if np.isnan(prev) or np.isnan(curr):
                    continue

                # Was negative → now positive (crossed above zero)
                if prev < 0 and curr >= 0:
                    print("[MACD] ⬆️ BULLISH zero-line cross "
                          "({:.6f} → {:.6f})".format(prev, curr))
                    return "BULLISH_ZERO_CROSS"

                # Was positive → now negative (crossed below zero)
                if prev > 0 and curr <= 0:
                    print("[MACD] ⬇️ BEARISH zero-line cross "
                          "({:.6f} → {:.6f})".format(prev, curr))
                    return "BEARISH_ZERO_CROSS"

            return "NONE"

        except Exception as e:
            print("[MACD] ❌ Zero cross detection error: {}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 6: ANALYZE HISTOGRAM
    # ============================================

    def analyze_histogram(self, histogram):
        """
        Analyzes the MACD histogram for momentum signals.

        The histogram shows the GAP between MACD and Signal.
        Its behavior reveals momentum changes:

        DIRECTION:
            GROWING  → bars getting taller (momentum increasing)
            SHRINKING → bars getting shorter (momentum fading)

        MOMENTUM:
            STRONG  → histogram consistently growing for 3+ bars
            WEAK    → histogram inconsistent or near zero
            NEUTRAL → histogram flat or choppy

        FLIP:
            True → histogram changed sign recently
                   (negative → positive or vice versa)
                   This is a powerful trend-change signal
            False → no sign change detected

        Checks the last 5 histogram values for analysis.

        Args:
            histogram (pd.Series): Histogram values

        Returns:
            dict: {
                "direction": "GROWING" | "SHRINKING" | "FLAT",
                "momentum": "STRONG" | "WEAK" | "NEUTRAL",
                "flip": True | False
            }
        """
        default_result = {
            "direction": "FLAT",
            "momentum": "NEUTRAL",
            "flip": False,
        }

        try:
            # ------ Validate input ------
            if histogram is None:
                return default_result

            valid_hist = histogram.dropna()

            if len(valid_hist) < 3:
                return default_result

            # ------ Get last 5 values ------
            check_count = min(5, len(valid_hist))
            recent = valid_hist.iloc[-check_count:].values

            # ------ DIRECTION: growing or shrinking? ------
            # Compare absolute values of consecutive bars
            # Growing = |recent bar| > |previous bar|
            abs_diffs = []
            for i in range(1, len(recent)):
                abs_diffs.append(abs(recent[i]) - abs(recent[i - 1]))

            if not abs_diffs:
                return default_result

            growing_count = sum(1 for d in abs_diffs if d > 0)
            shrinking_count = sum(1 for d in abs_diffs if d < 0)
            total_diffs = len(abs_diffs)

            if growing_count > shrinking_count:
                direction = "GROWING"
            elif shrinking_count > growing_count:
                direction = "SHRINKING"
            else:
                direction = "FLAT"

            # ------ MOMENTUM: how consistent is the direction? ------
            # STRONG: 75%+ of moves in same direction AND
            #         last 3 bars all going same way
            # WEAK: mixed signals
            # NEUTRAL: flat or too little data

            consistency = max(growing_count, shrinking_count) / total_diffs

            # Check last 3 bars for consecutive same-direction moves
            last_3_diffs = abs_diffs[-3:] if len(abs_diffs) >= 3 else abs_diffs

            if direction == "GROWING":
                last_3_consistent = all(d > 0 for d in last_3_diffs)
            elif direction == "SHRINKING":
                last_3_consistent = all(d < 0 for d in last_3_diffs)
            else:
                last_3_consistent = False

            if consistency >= 0.75 and last_3_consistent:
                momentum = "STRONG"
            elif consistency >= 0.5:
                momentum = "WEAK"
            else:
                momentum = "NEUTRAL"

            # ------ FLIP: did histogram change sign? ------
            # Check if any consecutive pair changed sign
            # in the last 3 bars
            flip = False
            flip_check = recent

            for i in range(1, len(flip_check)):
                prev_val = flip_check[i - 1]
                curr_val = flip_check[i]

                # Sign changed: negative → positive or positive → negative
                if prev_val * curr_val < 0:
                    flip = True
                    flip_sign = "positive" if curr_val > 0 else "negative"
                    print("[MACD] 🔄 Histogram FLIP to {} detected".format(
                        flip_sign
                    ))
                    break

            result = {
                "direction": direction,
                "momentum": momentum,
                "flip": flip,
            }

            print("[MACD] Histogram: {} | Momentum: {} | Flip: {}".format(
                direction, momentum, flip
            ))

            return result

        except Exception as e:
            print("[MACD] ❌ Histogram analysis error: {}".format(e))
            return default_result

    # ============================================
    # FUNCTION 7: DETECT DIVERGENCE
    # ============================================

    def detect_divergence(self, df, macd_line, lookback=20):
        """
        Detects bullish and bearish MACD divergences.

        Same concept as RSI divergence but using MACD values:

        BULLISH DIVERGENCE:
            Price makes LOWER LOW → sellers pushing down
            MACD makes HIGHER LOW → selling momentum weakening
            Interpretation: reversal upward likely

        BEARISH DIVERGENCE:
            Price makes HIGHER HIGH → buyers pushing up
            MACD makes LOWER HIGH → buying momentum weakening
            Interpretation: reversal downward likely

        Uses swing point detection (local minima/maxima)
        on both price and MACD to find divergence patterns.

        Args:
            df (DataFrame):       Must have 'close' column
            macd_line (pd.Series): MACD line values
            lookback (int):       Candles to look back (default 20)

        Returns:
            dict: {
                "bullish_divergence": True/False,
                "bearish_divergence": True/False
            }
        """
        default_result = {
            "bullish_divergence": False,
            "bearish_divergence": False,
        }

        try:
            # ------ Validate inputs ------
            if df is None or df.empty:
                return default_result

            if macd_line is None or macd_line.empty:
                return default_result

            # ------ Get last 'lookback' candles ------
            actual_lookback = min(lookback, len(df), len(macd_line))

            if actual_lookback < 5:
                return default_result

            price = df["close"].iloc[-actual_lookback:].values.astype(float)
            macd = macd_line.iloc[-actual_lookback:].values.astype(float)

            # ------ Remove positions with NaN MACD ------
            valid_mask = ~np.isnan(macd)

            if valid_mask.sum() < 5:
                return default_result

            # ------ Find swing lows (local minima) ------
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

            # ------ Check BULLISH divergence ------
            if len(swing_lows) >= 2:
                older_idx = swing_lows[-2]
                newer_idx = swing_lows[-1]

                # Price: lower low
                price_lower_low = price[newer_idx] < price[older_idx]

                # MACD: higher low
                macd_higher_low = macd[newer_idx] > macd[older_idx]

                if price_lower_low and macd_higher_low:
                    bullish_div = True
                    print("[MACD] 🔍 BULLISH DIVERGENCE | "
                          "Price: {:.2f}→{:.2f} (lower) | "
                          "MACD: {:.6f}→{:.6f} (higher)".format(
                              price[older_idx], price[newer_idx],
                              macd[older_idx], macd[newer_idx],
                          ))

            # ------ Check BEARISH divergence ------
            if len(swing_highs) >= 2:
                older_idx = swing_highs[-2]
                newer_idx = swing_highs[-1]

                # Price: higher high
                price_higher_high = price[newer_idx] > price[older_idx]

                # MACD: lower high
                macd_lower_high = macd[newer_idx] < macd[older_idx]

                if price_higher_high and macd_lower_high:
                    bearish_div = True
                    print("[MACD] 🔍 BEARISH DIVERGENCE | "
                          "Price: {:.2f}→{:.2f} (higher) | "
                          "MACD: {:.6f}→{:.6f} (lower)".format(
                              price[older_idx], price[newer_idx],
                              macd[older_idx], macd[newer_idx],
                          ))

            return {
                "bullish_divergence": bullish_div,
                "bearish_divergence": bearish_div,
            }

        except Exception as e:
            print("[MACD] ❌ Divergence detection error: {}".format(e))
            return default_result

    # ============================================
    # FUNCTION 8: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        MAIN ANALYSIS FUNCTION — Runs all MACD checks and
        produces a scored trading signal.

        Pipeline:
        1. Calculate MACD, Signal, Histogram
        2. Detect MACD/Signal crossover
        3. Detect zero-line cross
        4. Analyze histogram momentum
        5. Detect divergences
        6. Calculate composite score (0-100)
        7. Determine direction and confidence

        SCORING SYSTEM:
        Base score = 50 (neutral center)

        LONG factors (add to score):
        +15  Bullish crossover (MACD crosses above Signal)
        +10  Bullish zero cross (MACD crosses above zero)
        +10  Histogram growing positive
        +15  Histogram flip to positive
        +20  Bullish divergence

        SHORT factors (subtract from score):
        -15  Bearish crossover (MACD crosses below Signal)
        -10  Bearish zero cross (MACD crosses below zero)
        -10  Histogram growing negative
        -15  Histogram flip to negative
        -20  Bearish divergence

        Score clamped to 0-100 range.

        DIRECTION MAPPING:
         0-30  → Strong SHORT  | confidence = (50-score) * 2
        30-45  → Weak SHORT    | confidence = (50-score) * 2
        45-55  → NEUTRAL       | confidence = 0
        55-70  → Weak LONG     | confidence = (score-50) * 2
        70-100 → Strong LONG   | confidence = (score-50) * 2

        Args:
            df (DataFrame): Price data with at least 'close' column

        Returns:
            dict: {
                "brain": "MACD",
                "direction": "LONG" / "SHORT" / "NEUTRAL",
                "confidence": 0-100 (float),
                "macd_value": current MACD (float),
                "signal_value": current Signal (float),
                "histogram_value": current Histogram (float),
                "details": {
                    "crossover": str,
                    "zero_cross": str,
                    "histogram": dict,
                    "divergence": bool
                }
            }
        """
        # ------ Default neutral result ------
        neutral_result = {
            "brain": "MACD",
            "direction": "NEUTRAL",
            "confidence": 0,
            "macd_value": 0.0,
            "signal_value": 0.0,
            "histogram_value": 0.0,
            "details": {
                "crossover": "NONE",
                "zero_cross": "NONE",
                "histogram": {
                    "direction": "FLAT",
                    "momentum": "NEUTRAL",
                    "flip": False,
                },
                "divergence": False,
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input DataFrame
            # ============================================
            if df is None or df.empty:
                print("[MACD] ⚠️ No data provided for analysis")
                return neutral_result

            if "close" not in df.columns:
                print("[MACD] ⚠️ 'close' column missing")
                return neutral_result

            if len(df) < self.min_data_points:
                print("[MACD] ⚠️ Need {} rows, got {}".format(
                    self.min_data_points, len(df)
                ))
                return neutral_result

            # ============================================
            # STEP 2: Calculate MACD components
            # ============================================
            macd_data = self.calculate_macd(df)

            if macd_data is None:
                print("[MACD] ⚠️ MACD calculation returned None")
                return neutral_result

            macd_line = macd_data["macd_line"]
            signal_line = macd_data["signal_line"]
            histogram = macd_data["histogram"]

            # ------ Get current values ------
            valid_macd = macd_line.dropna()
            valid_signal = signal_line.dropna()
            valid_hist = histogram.dropna()

            if len(valid_macd) == 0 or len(valid_signal) == 0:
                print("[MACD] ⚠️ No valid MACD/Signal values")
                return neutral_result

            current_macd = float(valid_macd.iloc[-1])
            current_signal = float(valid_signal.iloc[-1])
            current_hist = float(valid_hist.iloc[-1]) if len(valid_hist) > 0 else 0.0

            # ============================================
            # STEP 3: Run all sub-analyses
            # ============================================

            # 3a: Detect MACD/Signal crossover
            crossover = self.detect_crossover(macd_line, signal_line)

            # 3b: Detect zero-line cross
            zero_cross = self.detect_zero_cross(macd_line)

            # 3c: Analyze histogram
            hist_analysis = self.analyze_histogram(histogram)

            # 3d: Detect divergences
            divergence = self.detect_divergence(df, macd_line, lookback=20)
            has_bullish_div = divergence["bullish_divergence"]
            has_bearish_div = divergence["bearish_divergence"]

            # ============================================
            # STEP 4: Calculate composite score
            # ============================================
            score = 50.0  # Neutral center

            # ------ LONG factors (add to score) ------

            # Bullish crossover: +15 points
            if crossover == "BULLISH_CROSS":
                score += 15.0
                print("[MACD] 📈 +15 pts | BULLISH crossover")

            # Bullish zero cross: +10 points
            if zero_cross == "BULLISH_ZERO_CROSS":
                score += 10.0
                print("[MACD] 📈 +10 pts | BULLISH zero cross")

            # Histogram growing positive: +10 points
            # Condition: histogram > 0 AND growing
            if (current_hist > 0 and
                    hist_analysis["direction"] == "GROWING"):
                score += 10.0
                print("[MACD] 📈 +10 pts | Histogram growing positive")

            # Histogram flip to positive: +15 points
            if hist_analysis["flip"] and current_hist > 0:
                score += 15.0
                print("[MACD] 📈 +15 pts | Histogram FLIP to positive")

            # Bullish divergence: +20 points
            if has_bullish_div:
                score += 20.0
                print("[MACD] 📈 +20 pts | BULLISH divergence")

            # ------ SHORT factors (subtract from score) ------

            # Bearish crossover: -15 points
            if crossover == "BEARISH_CROSS":
                score -= 15.0
                print("[MACD] 📉 -15 pts | BEARISH crossover")

            # Bearish zero cross: -10 points
            if zero_cross == "BEARISH_ZERO_CROSS":
                score -= 10.0
                print("[MACD] 📉 -10 pts | BEARISH zero cross")

            # Histogram growing negative: -10 points
            # Condition: histogram < 0 AND growing (getting more negative)
            if (current_hist < 0 and
                    hist_analysis["direction"] == "GROWING"):
                score -= 10.0
                print("[MACD] 📉 -10 pts | Histogram growing negative")

            # Histogram flip to negative: -15 points
            if hist_analysis["flip"] and current_hist < 0:
                score -= 15.0
                print("[MACD] 📉 -15 pts | Histogram FLIP to negative")

            # Bearish divergence: -20 points
            if has_bearish_div:
                score -= 20.0
                print("[MACD] 📉 -20 pts | BEARISH divergence")

            # ============================================
            # STEP 5: Clamp score to 0-100
            # ============================================
            score = max(0.0, min(100.0, score))

            # ============================================
            # STEP 6: Determine direction and confidence
            # ============================================

            if score < 30:
                direction = "SHORT"
                confidence = (50.0 - score) * 2.0

            elif score < 45:
                direction = "SHORT"
                confidence = (50.0 - score) * 2.0

            elif score <= 55:
                direction = "NEUTRAL"
                confidence = 0.0

            elif score <= 70:
                direction = "LONG"
                confidence = (score - 50.0) * 2.0

            else:
                direction = "LONG"
                confidence = (score - 50.0) * 2.0

            # Clamp confidence
            confidence = max(0.0, min(100.0, round(confidence, 2)))

            # Divergence flag for details
            divergence_relevant = has_bullish_div or has_bearish_div

            # ============================================
            # STEP 7: Build result dictionary
            # ============================================
            result = {
                "brain": "MACD",
                "direction": direction,
                "confidence": confidence,
                "macd_value": round(current_macd, 6),
                "signal_value": round(current_signal, 6),
                "histogram_value": round(current_hist, 6),
                "details": {
                    "crossover": crossover,
                    "zero_cross": zero_cross,
                    "histogram": hist_analysis,
                    "divergence": divergence_relevant,
                },
            }

            # Store for later reference
            self.results = result

            # ============================================
            # STEP 8: Log the analysis summary
            # ============================================
            print("\n[MACD] ═══════════════════════════════════")
            print("[MACD]  MACD Analysis Complete")
            print("[MACD]  MACD Value   : {:.6f}".format(current_macd))
            print("[MACD]  Signal Value : {:.6f}".format(current_signal))
            print("[MACD]  Histogram    : {:.6f}".format(current_hist))
            print("[MACD]  Crossover    : {}".format(crossover))
            print("[MACD]  Zero Cross   : {}".format(zero_cross))
            print("[MACD]  Hist Dir     : {}".format(hist_analysis["direction"]))
            print("[MACD]  Hist Momentum: {}".format(hist_analysis["momentum"]))
            print("[MACD]  Hist Flip    : {}".format(hist_analysis["flip"]))
            print("[MACD]  Divergence   : {}".format(
                "YES" if divergence_relevant else "No"
            ))
            print("[MACD]  Raw Score    : {:.1f}/100".format(score))
            print("[MACD]  Direction    : {}".format(direction))
            print("[MACD]  Confidence   : {:.1f}%".format(confidence))
            print("[MACD] ═══════════════════════════════════\n")

            return result

        except Exception as e:
            print("[MACD] ❌ Analysis error: {}".format(e))
            return neutral_result


# ==================================================
# MODULE-LEVEL SINGLETON INSTANCE
# ==================================================
# Every module imports this same instance:
#
#   from algorithms.macd import macd_analyzer
#   result = macd_analyzer.analyze(dataframe)
#
# result = {
#     "brain": "MACD",
#     "direction": "LONG" / "SHORT" / "NEUTRAL",
#     "confidence": 0-100,
#     "macd_value": float,
#     "signal_value": float,
#     "histogram_value": float,
#     "details": {...}
# }
# ==================================================

macd_analyzer = MACDAnalyzer()

print("[MACD] ✅ MACD module loaded and ready")