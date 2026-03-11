# ============================================
# CRYPTO SIGNAL BOT - EMA CROSSOVER ANALYZER
# ============================================
# Brain #5 of 7: EMA Crossover & Trend Filter
#
# This is the TREND DIRECTION brain — the most
# important filter in the entire system. Trading
# against the trend is the #1 cause of losses.
#
# This brain answers: "Is the market going UP
# or DOWN right now?"
#
# EMA Periods Used:
#   EMA 9   → Ultra short-term (scalping)
#   EMA 21  → Short-term (swing)
#   EMA 50  → Medium-term (trend)
#   EMA 100 → Long-term (major trend)
#   EMA 200 → Very long-term (overall direction)
#
# Key Signals:
#   Perfect alignment (9>21>50>100>200) → strong trend
#   Golden cross (EMA50 > EMA200) → major bullish
#   Death cross (EMA50 < EMA200) → major bearish
#   Price above all EMAs → bullish bias
#   Price below all EMAs → bearish bias
#   EMA bounce → trend continuation
#
# All calculations done FROM SCRATCH.
# Handles variable data lengths gracefully.
#
# Usage:
#   from algorithms.ema_crossover import ema_crossover_analyzer
#   result = ema_crossover_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class EMACrossoverAnalyzer:
    """
    EMA Crossover and trend direction analyzer.

    Calculates 5 EMAs at different periods, checks
    their alignment, crossovers, slopes, distances,
    and price position to determine the overall
    market trend direction.

    Attributes:
        ema_periods (list):     EMA periods to calculate
        min_data_points (int):  Minimum candles needed
        results (dict):         Stores latest analysis
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize the EMA Crossover Analyzer.

        Sets up:
        - EMA periods: [9, 21, 50, 100, 200]
        - Minimum data requirement: 50 candles
        - Crossover pairs to monitor
        """
        # ------ EMA periods from shortest to longest ------
        self.ema_periods = [9, 21, 50, 100, 200]

        # ------ Crossover pairs to check: (fast, slow) ------
        self.crossover_pairs = [
            (9, 21),    # Short-term cross
            (21, 50),   # Medium-term cross
            (50, 100),  # Long-term cross
            (50, 200),  # Golden/Death cross
        ]

        # ------ Minimum data: 50 candles for basic analysis ------
        # EMA50 needs 50 candles for first valid value
        # Below 50 → return NEUTRAL
        self.min_data_points = 50

        # ------ Storage for latest analysis results ------
        self.results = {}

        print("[EMA] ✅ Analyzer initialized | "
              "Periods: {}".format(self.ema_periods))

    # ============================================
    # FUNCTION 2: CALCULATE EMA (From Scratch)
    # ============================================

    def calculate_ema(self, series, period):
        """
        Calculates Exponential Moving Average from scratch.

        EMA gives more weight to recent prices, making it
        more responsive than SMA.

        Formula:
            multiplier = 2 / (period + 1)
            EMA[period-1] = SMA of first 'period' values
            EMA[i] = (value[i] - EMA[i-1]) × multiplier + EMA[i-1]

        Args:
            series (pd.Series): Close prices (float)
            period (int):       EMA period

        Returns:
            pd.Series: EMA values with same index.
                      First (period-1) values are NaN.
                      Returns None if insufficient data.
        """
        try:
            # ------ Validate inputs ------
            if series is None or len(series) == 0:
                return None

            if period <= 0:
                return None

            if len(series) < period:
                # Not enough data for this EMA period
                return None

            # ------ Convert to numpy for speed ------
            values = series.astype(float).values
            data_length = len(values)

            # ------ EMA smoothing multiplier ------
            multiplier = 2.0 / (period + 1.0)

            # ------ Pre-allocate with NaN ------
            ema_values = np.full(data_length, np.nan, dtype=np.float64)

            # ------ Seed: SMA of first 'period' values ------
            initial_window = values[:period]
            valid_initial = initial_window[~np.isnan(initial_window)]

            if len(valid_initial) == 0:
                return None

            ema_values[period - 1] = np.mean(valid_initial)

            # ------ Compute EMA recursively ------
            for i in range(period, data_length):
                current_val = values[i]

                if np.isnan(current_val):
                    # Carry forward previous EMA on NaN
                    ema_values[i] = ema_values[i - 1]
                else:
                    ema_values[i] = (
                        (current_val - ema_values[i - 1]) * multiplier
                        + ema_values[i - 1]
                    )

            # ------ Build pandas Series ------
            ema_series = pd.Series(
                ema_values,
                index=series.index,
                name="EMA_{}".format(period),
                dtype=np.float64,
            )

            return ema_series

        except Exception as e:
            print("[EMA] ❌ EMA({}) calculation error: {}".format(period, e))
            return None

    # ============================================
    # FUNCTION 3: CALCULATE ALL EMAs
    # ============================================

    def calculate_all_emas(self, df):
        """
        Calculates all 5 EMAs for the given DataFrame.

        Handles variable data lengths:
        - >= 200 candles → all 5 EMAs calculated
        - >= 100 candles → EMA 9, 21, 50, 100 (skip 200)
        - >= 50 candles  → EMA 9, 21, 50 (skip 100, 200)
        - < 50 candles   → returns None (insufficient data)

        Args:
            df (DataFrame): Must have 'close' column

        Returns:
            dict: {
                "ema_9": pd.Series or None,
                "ema_21": pd.Series or None,
                "ema_50": pd.Series or None,
                "ema_100": pd.Series or None,
                "ema_200": pd.Series or None,
                "available_periods": [list of calculated periods]
            }
            Returns None on critical error.
        """
        try:
            # ------ Validate input ------
            if df is None or df.empty:
                print("[EMA] ⚠️ Empty DataFrame received")
                return None

            if "close" not in df.columns:
                print("[EMA] ⚠️ 'close' column missing")
                return None

            close = df["close"].astype(float)
            data_length = len(close)

            if data_length < self.min_data_points:
                print("[EMA] ⚠️ Need {} candles, got {}".format(
                    self.min_data_points, data_length
                ))
                return None

            # ------ Calculate each EMA if enough data ------
            result = {
                "ema_9": None,
                "ema_21": None,
                "ema_50": None,
                "ema_100": None,
                "ema_200": None,
                "available_periods": [],
            }

            for period in self.ema_periods:
                key = "ema_{}".format(period)

                if data_length >= period:
                    ema = self.calculate_ema(close, period)
                    if ema is not None:
                        result[key] = ema
                        result["available_periods"].append(period)

            # ------ Verify minimum EMAs calculated ------
            # Need at least EMA 9 and 21 for basic analysis
            if 9 not in result["available_periods"] or \
               21 not in result["available_periods"]:
                print("[EMA] ⚠️ Could not calculate minimum EMAs")
                return None

            available = result["available_periods"]
            print("[EMA] Calculated EMAs: {} | "
                  "Data length: {}".format(available, data_length))

            return result

        except Exception as e:
            print("[EMA] ❌ EMA calculation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 4: CHECK EMA ALIGNMENT
    # ============================================

    def check_ema_alignment(self, emas):
        """
        Checks if EMAs are aligned at the latest candle.

        Perfect bullish alignment means all EMAs are stacked:
        EMA9 > EMA21 > EMA50 > EMA100 > EMA200

        Alignment levels (bullish):
        - PERFECT_BULLISH:  all 5 aligned (or all available)
        - STRONG_BULLISH:   at least 4 aligned
        - MODERATE_BULLISH: EMA9 > EMA21 > EMA50
        - WEAK_BULLISH:     EMA9 > EMA21 only
        - TANGLED:          no clear order

        Same levels exist for bearish (reversed).

        Also counts how many consecutive EMA pairs are
        bullish or bearish aligned.

        Args:
            emas (dict): Output from calculate_all_emas()

        Returns:
            dict: {
                "alignment": str (level name),
                "bullish_count": int,
                "bearish_count": int
            }
        """
        default = {
            "alignment": "TANGLED",
            "bullish_count": 0,
            "bearish_count": 0,
        }

        try:
            if emas is None:
                return default

            # ------ Get latest valid value for each available EMA ------
            available = emas.get("available_periods", [])

            if len(available) < 2:
                return default

            # Build ordered list of (period, latest_value)
            latest_values = []
            for period in sorted(available):
                key = "ema_{}".format(period)
                series = emas.get(key)
                if series is not None:
                    valid = series.dropna()
                    if len(valid) > 0:
                        latest_values.append((period, float(valid.iloc[-1])))

            if len(latest_values) < 2:
                return default

            # ------ Count bullish and bearish pairs ------
            # Bullish pair: faster EMA > slower EMA
            # Check consecutive pairs in order
            bullish_count = 0
            bearish_count = 0

            for i in range(len(latest_values) - 1):
                fast_val = latest_values[i][1]   # Shorter period
                slow_val = latest_values[i + 1][1]  # Longer period

                if fast_val > slow_val:
                    bullish_count += 1
                elif fast_val < slow_val:
                    bearish_count += 1

            total_pairs = len(latest_values) - 1

            # ------ Determine alignment level ------

            # Perfect: ALL pairs aligned same direction
            if bullish_count == total_pairs:
                if total_pairs >= 4:
                    alignment = "PERFECT_BULLISH"
                elif total_pairs >= 3:
                    alignment = "STRONG_BULLISH"
                elif total_pairs >= 2:
                    alignment = "MODERATE_BULLISH"
                else:
                    alignment = "WEAK_BULLISH"

            elif bearish_count == total_pairs:
                if total_pairs >= 4:
                    alignment = "PERFECT_BEARISH"
                elif total_pairs >= 3:
                    alignment = "STRONG_BEARISH"
                elif total_pairs >= 2:
                    alignment = "MODERATE_BEARISH"
                else:
                    alignment = "WEAK_BEARISH"

            # Partial alignment: check from the shortest EMAs
            elif bullish_count > bearish_count:
                # Check which specific EMAs are bullish
                # latest_values is sorted by period ascending
                vals = [v[1] for v in latest_values]

                if len(vals) >= 3 and vals[0] > vals[1] > vals[2]:
                    alignment = "MODERATE_BULLISH"
                elif len(vals) >= 2 and vals[0] > vals[1]:
                    alignment = "WEAK_BULLISH"
                else:
                    alignment = "TANGLED"

            elif bearish_count > bullish_count:
                vals = [v[1] for v in latest_values]

                if len(vals) >= 3 and vals[0] < vals[1] < vals[2]:
                    alignment = "MODERATE_BEARISH"
                elif len(vals) >= 2 and vals[0] < vals[1]:
                    alignment = "WEAK_BEARISH"
                else:
                    alignment = "TANGLED"

            else:
                alignment = "TANGLED"

            if "PERFECT" in alignment or "STRONG" in alignment:
                print("[EMA] 🏗️ Alignment: {} | "
                      "Bull: {} | Bear: {}".format(
                          alignment, bullish_count, bearish_count
                      ))

            return {
                "alignment": alignment,
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
            }

        except Exception as e:
            print("[EMA] ❌ Alignment check error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 5: DETECT CROSSOVERS
    # ============================================

    def detect_crossovers(self, emas, lookback=5):
        """
        Detects EMA crossovers in the last N candles.

        Checks these pairs:
        - (9, 21):  Short-term trend cross
        - (21, 50): Medium-term trend cross
        - (50, 100): Long-term trend cross
        - (50, 200): Golden Cross / Death Cross

        Golden Cross: EMA50 crosses ABOVE EMA200
        Death Cross:  EMA50 crosses BELOW EMA200

        For each pair, scans backward from the most recent
        candle to find the latest crossover event.

        Args:
            emas (dict):    Output from calculate_all_emas()
            lookback (int): How many candles back to scan

        Returns:
            dict: {
                "crossovers": list of crossover events,
                "golden_cross": True/False,
                "death_cross": True/False,
                "most_recent": "BULLISH"/"BEARISH"/"NONE"
            }
        """
        default = {
            "crossovers": [],
            "golden_cross": False,
            "death_cross": False,
            "most_recent": "NONE",
        }

        try:
            if emas is None:
                return default

            available = emas.get("available_periods", [])
            crossovers_found = []
            golden = False
            death = False

            for fast_period, slow_period in self.crossover_pairs:
                # Skip if either EMA not available
                if fast_period not in available or slow_period not in available:
                    continue

                fast_key = "ema_{}".format(fast_period)
                slow_key = "ema_{}".format(slow_period)

                fast_series = emas[fast_key]
                slow_series = emas[slow_key]

                if fast_series is None or slow_series is None:
                    continue

                # Calculate difference: fast - slow
                diff = fast_series - slow_series
                valid_diff = diff.dropna()

                if len(valid_diff) < 2:
                    continue

                # Scan last N candles for crossover
                check_count = min(lookback, len(valid_diff))
                recent = valid_diff.iloc[-check_count:]
                values = recent.values

                for i in range(len(values) - 1, 0, -1):
                    prev = values[i - 1]
                    curr = values[i]

                    if np.isnan(prev) or np.isnan(curr):
                        continue

                    candles_ago = len(values) - 1 - i

                    # Bullish cross: was below, now above
                    if prev < 0 and curr >= 0:
                        cross_type = "BULLISH"
                        crossovers_found.append({
                            "fast": fast_period,
                            "slow": slow_period,
                            "type": cross_type,
                            "candles_ago": candles_ago,
                        })

                        if fast_period == 50 and slow_period == 200:
                            golden = True
                            print("[EMA] ⭐ GOLDEN CROSS detected! "
                                  "(EMA50 crossed above EMA200)")
                        else:
                            print("[EMA] ↗️ Bullish cross: EMA{}/EMA{} "
                                  "({} candles ago)".format(
                                      fast_period, slow_period,
                                      candles_ago
                                  ))
                        break  # Only most recent cross per pair

                    # Bearish cross: was above, now below
                    if prev > 0 and curr <= 0:
                        cross_type = "BEARISH"
                        crossovers_found.append({
                            "fast": fast_period,
                            "slow": slow_period,
                            "type": cross_type,
                            "candles_ago": candles_ago,
                        })

                        if fast_period == 50 and slow_period == 200:
                            death = True
                            print("[EMA] 💀 DEATH CROSS detected! "
                                  "(EMA50 crossed below EMA200)")
                        else:
                            print("[EMA] ↘️ Bearish cross: EMA{}/EMA{} "
                                  "({} candles ago)".format(
                                      fast_period, slow_period,
                                      candles_ago
                                  ))
                        break

            # Determine most recent crossover direction
            most_recent = "NONE"
            if crossovers_found:
                # Sort by candles_ago ascending (most recent first)
                crossovers_found.sort(key=lambda x: x["candles_ago"])
                most_recent = crossovers_found[0]["type"]

            return {
                "crossovers": crossovers_found,
                "golden_cross": golden,
                "death_cross": death,
                "most_recent": most_recent,
            }

        except Exception as e:
            print("[EMA] ❌ Crossover detection error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 6: CHECK PRICE POSITION
    # ============================================

    def check_price_position(self, df, emas):
        """
        Checks where current price sits relative to all EMAs.

        Price above an EMA = bullish bias for that timeframe.
        Price below an EMA = bearish bias for that timeframe.

        Positions:
        - ABOVE_ALL: price above every available EMA (bullish)
        - BELOW_ALL: price below every available EMA (bearish)
        - MIXED: price between some EMAs (consolidation)

        Args:
            df (DataFrame): Must have 'close' column
            emas (dict):    Output from calculate_all_emas()

        Returns:
            dict: {
                "above_ema9": True/False,
                "above_ema21": True/False,
                "above_ema50": True/False,
                "above_ema100": True/False,
                "above_ema200": True/False,
                "above_count": int,
                "below_count": int,
                "position": "ABOVE_ALL"/"BELOW_ALL"/"MIXED"
            }
        """
        default = {
            "above_ema9": False,
            "above_ema21": False,
            "above_ema50": False,
            "above_ema100": False,
            "above_ema200": False,
            "above_count": 0,
            "below_count": 0,
            "position": "MIXED",
        }

        try:
            if df is None or df.empty or emas is None:
                return default

            current_price = float(df["close"].iloc[-1])
            available = emas.get("available_periods", [])

            if not available:
                return default

            above_count = 0
            below_count = 0
            total_checked = 0
            result = dict(default)

            for period in self.ema_periods:
                key = "ema_{}".format(period)
                above_key = "above_ema{}".format(period)

                if period not in available or emas.get(key) is None:
                    # EMA not available — leave as False
                    continue

                series = emas[key]
                valid = series.dropna()

                if len(valid) == 0:
                    continue

                ema_val = float(valid.iloc[-1])
                total_checked += 1

                if current_price > ema_val:
                    result[above_key] = True
                    above_count += 1
                else:
                    below_count += 1

            result["above_count"] = above_count
            result["below_count"] = below_count

            # Determine position
            if total_checked > 0:
                if above_count == total_checked:
                    result["position"] = "ABOVE_ALL"
                elif below_count == total_checked:
                    result["position"] = "BELOW_ALL"
                else:
                    result["position"] = "MIXED"

            return result

        except Exception as e:
            print("[EMA] ❌ Price position error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 7: CALCULATE EMA SLOPES
    # ============================================

    def calculate_ema_slopes(self, emas, lookback=5):
        """
        Calculates the slope of each EMA over last N candles.

        Slope shows if an EMA is rising, falling, or flat.
        All EMAs sloping same direction = confirmed trend.

        Slope = (current_ema - ema_N_ago) / ema_N_ago × 100

        Classification:
        - RISING:  slope > +0.05% (upward)
        - FALLING: slope < -0.05% (downward)
        - FLAT:    slope within ±0.05% (sideways)

        Args:
            emas (dict):    Output from calculate_all_emas()
            lookback (int): Candles to measure slope over

        Returns:
            dict: {
                "ema_9_slope": str,
                "ema_21_slope": str,
                ...,
                "all_rising": True/False,
                "all_falling": True/False,
                "overall_slope": "BULLISH"/"BEARISH"/"NEUTRAL"
            }
        """
        default = {
            "ema_9_slope": "FLAT",
            "ema_21_slope": "FLAT",
            "ema_50_slope": "FLAT",
            "ema_100_slope": "FLAT",
            "ema_200_slope": "FLAT",
            "all_rising": False,
            "all_falling": False,
            "overall_slope": "NEUTRAL",
        }

        try:
            if emas is None:
                return default

            available = emas.get("available_periods", [])

            if not available:
                return default

            result = dict(default)
            slopes = []  # Collect classified slopes for summary

            for period in self.ema_periods:
                key = "ema_{}".format(period)
                slope_key = "ema_{}_slope".format(period)

                if period not in available or emas.get(key) is None:
                    continue

                series = emas[key]
                valid = series.dropna()

                if len(valid) < lookback + 1:
                    continue

                # Current and lookback-ago values
                current = float(valid.iloc[-1])
                ago = float(valid.iloc[-(lookback + 1)])

                if ago == 0:
                    continue

                # Slope as percentage change
                slope_pct = ((current - ago) / ago) * 100.0

                # Classify
                if slope_pct > 0.05:
                    classification = "RISING"
                elif slope_pct < -0.05:
                    classification = "FALLING"
                else:
                    classification = "FLAT"

                result[slope_key] = classification
                slopes.append(classification)

            # ------ Summary flags ------
            if slopes:
                result["all_rising"] = all(s == "RISING" for s in slopes)
                result["all_falling"] = all(s == "FALLING" for s in slopes)

                rising_count = slopes.count("RISING")
                falling_count = slopes.count("FALLING")

                if rising_count > falling_count:
                    result["overall_slope"] = "BULLISH"
                elif falling_count > rising_count:
                    result["overall_slope"] = "BEARISH"
                else:
                    result["overall_slope"] = "NEUTRAL"

                if result["all_rising"]:
                    print("[EMA] 📈 ALL EMAs sloping UP")
                elif result["all_falling"]:
                    print("[EMA] 📉 ALL EMAs sloping DOWN")

            return result

        except Exception as e:
            print("[EMA] ❌ Slope calculation error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 8: CALCULATE EMA DISTANCE
    # ============================================

    def calculate_ema_distance(self, emas):
        """
        Calculates percentage distance between EMA pairs.

        Distance shows trend strength and overextension:
        - EMAs far apart (>2%) → strong trend, possibly overextended
        - EMAs close together (<0.3%) → consolidation / no trend
        - EMAs converging → trend change approaching
        - EMAs diverging → trend strengthening

        Checked pairs: (9,21), (21,50), (50,200)

        Args:
            emas (dict): Output from calculate_all_emas()

        Returns:
            dict: {
                "ema_9_21_distance": float %,
                "ema_21_50_distance": float %,
                "ema_50_200_distance": float %,
                "spread_condition": "WIDE"/"NORMAL"/"TIGHT"/"CONVERGING",
                "overextended": True/False
            }
        """
        default = {
            "ema_9_21_distance": 0.0,
            "ema_21_50_distance": 0.0,
            "ema_50_200_distance": 0.0,
            "spread_condition": "NORMAL",
            "overextended": False,
        }

        try:
            if emas is None:
                return default

            available = emas.get("available_periods", [])
            result = dict(default)

            # ------ Calculate distances for each pair ------
            distance_pairs = [
                (9, 21, "ema_9_21_distance"),
                (21, 50, "ema_21_50_distance"),
                (50, 200, "ema_50_200_distance"),
            ]

            distances = []

            for fast_p, slow_p, dist_key in distance_pairs:
                if fast_p not in available or slow_p not in available:
                    continue

                fast_key = "ema_{}".format(fast_p)
                slow_key = "ema_{}".format(slow_p)

                fast_s = emas.get(fast_key)
                slow_s = emas.get(slow_key)

                if fast_s is None or slow_s is None:
                    continue

                fast_valid = fast_s.dropna()
                slow_valid = slow_s.dropna()

                if len(fast_valid) == 0 or len(slow_valid) == 0:
                    continue

                fast_val = float(fast_valid.iloc[-1])
                slow_val = float(slow_valid.iloc[-1])

                if slow_val == 0:
                    continue

                distance_pct = abs(fast_val - slow_val) / slow_val * 100.0
                result[dist_key] = round(distance_pct, 4)
                distances.append(distance_pct)

            # ------ Determine spread condition ------
            if distances:
                avg_distance = sum(distances) / len(distances)

                if avg_distance > 2.0:
                    result["spread_condition"] = "WIDE"
                    result["overextended"] = True
                elif avg_distance > 0.8:
                    result["spread_condition"] = "NORMAL"
                elif avg_distance > 0.3:
                    result["spread_condition"] = "TIGHT"
                else:
                    result["spread_condition"] = "CONVERGING"

                # Check for convergence: is distance shrinking?
                # Compare 9/21 distance vs 21/50 distance
                if len(distances) >= 2:
                    if distances[0] < distances[1] * 0.5:
                        # Short-term EMAs much closer than
                        # medium-term → converging
                        result["spread_condition"] = "CONVERGING"

            return result

        except Exception as e:
            print("[EMA] ❌ Distance calculation error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 9: DETECT EMA BOUNCE
    # ============================================

    def detect_ema_bounce(self, df, emas, tolerance_percent=0.3):
        """
        Detects price bouncing off an EMA (dynamic support/resistance).

        A bounce occurs when price approaches an EMA, touches
        or comes within tolerance, then moves away. This is a
        trend continuation signal.

        In uptrend: price pulls back to EMA → bounces UP
        In downtrend: price rallies to EMA → bounces DOWN

        Priority: checks shorter EMAs first (EMA9, then 21, etc.)
        Only returns the FIRST bounce found (most relevant).

        Detection logic (for bounce UP):
        1. Some candle in last 5 had its low within tolerance
           of an EMA value
        2. Current close is ABOVE that EMA
        3. Current close > that candle's close (recovered)

        Args:
            df (DataFrame):           Must have 'close', 'high', 'low'
            emas (dict):              Output from calculate_all_emas()
            tolerance_percent (float): How close = "touched" (default 0.3%)

        Returns:
            dict: {
                "bounce_detected": True/False,
                "bounced_from": "EMA_9"/"EMA_21"/... or None,
                "bounce_direction": "UP"/"DOWN"/None,
                "bounce_strength": 0-100
            }
        """
        default = {
            "bounce_detected": False,
            "bounced_from": None,
            "bounce_direction": None,
            "bounce_strength": 0,
        }

        try:
            if df is None or df.empty or emas is None:
                return default

            required = ["close", "high", "low"]
            for col in required:
                if col not in df.columns:
                    return default

            available = emas.get("available_periods", [])

            if not available:
                return default

            # Check last 5 candles
            check_count = min(5, len(df))
            recent_df = df.iloc[-check_count:]

            close = recent_df["close"].astype(float).values
            high = recent_df["high"].astype(float).values
            low = recent_df["low"].astype(float).values

            current_close = close[-1]

            # ------ Check each EMA (shortest first) ------
            for period in sorted(available):
                key = "ema_{}".format(period)
                series = emas.get(key)

                if series is None:
                    continue

                # Get EMA values for the recent candles
                recent_ema = series.iloc[-check_count:]
                valid_mask = recent_ema.notna()

                if valid_mask.sum() < 2:
                    continue

                ema_vals = recent_ema.values.astype(float)
                current_ema = ema_vals[-1]

                if np.isnan(current_ema) or current_ema == 0:
                    continue

                tolerance = current_ema * (tolerance_percent / 100.0)

                # ------ Check for BOUNCE UP ------
                # Some candle's low was near EMA, current close above EMA
                for i in range(len(low) - 1):
                    if np.isnan(ema_vals[i]):
                        continue

                    dist_low = abs(low[i] - ema_vals[i])

                    if dist_low <= tolerance and current_close > current_ema:
                        # Confirm upward movement after touch
                        if current_close > close[i]:
                            # Strength: how far price moved from EMA
                            move_pct = abs(
                                current_close - current_ema
                            ) / current_ema * 100.0
                            strength = min(100, int(move_pct * 50))

                            print("[EMA] ⬆️ BOUNCE UP from EMA_{} "
                                  "detected | Strength: {}".format(
                                      period, strength
                                  ))

                            return {
                                "bounce_detected": True,
                                "bounced_from": "EMA_{}".format(period),
                                "bounce_direction": "UP",
                                "bounce_strength": strength,
                            }

                # ------ Check for BOUNCE DOWN ------
                for i in range(len(high) - 1):
                    if np.isnan(ema_vals[i]):
                        continue

                    dist_high = abs(high[i] - ema_vals[i])

                    if dist_high <= tolerance and current_close < current_ema:
                        if current_close < close[i]:
                            move_pct = abs(
                                current_ema - current_close
                            ) / current_ema * 100.0
                            strength = min(100, int(move_pct * 50))

                            print("[EMA] ⬇️ BOUNCE DOWN from EMA_{} "
                                  "detected | Strength: {}".format(
                                      period, strength
                                  ))

                            return {
                                "bounce_detected": True,
                                "bounced_from": "EMA_{}".format(period),
                                "bounce_direction": "DOWN",
                                "bounce_strength": strength,
                            }

            return default

        except Exception as e:
            print("[EMA] ❌ Bounce detection error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 10: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        MAIN ANALYSIS FUNCTION — Runs all EMA checks and
        produces a scored trading signal.

        Pipeline:
        1. Calculate all available EMAs
        2. Check EMA alignment
        3. Detect crossovers (including Golden/Death cross)
        4. Check price position relative to EMAs
        5. Calculate EMA slopes
        6. Calculate EMA distances
        7. Detect EMA bounces
        8. Calculate composite score (0-100)
        9. Determine direction and confidence

        SCORING SYSTEM:
        Base score = 50 (neutral center)

        LONG factors (add to score):
        +20  Perfect bullish alignment
        +15  Strong bullish alignment
        +10  Moderate bullish alignment
        +5   Weak bullish alignment
        +10  Price above all EMAs
        +10  All EMAs sloping up
        +15  Golden cross detected
        +8   EMA9/21 bullish cross
        +10  EMA21/50 bullish cross
        +10  Bounce up from EMA support
        +5   EMAs diverging upward (wide spread)

        SHORT factors (subtract from score):
        -20  Perfect bearish alignment
        -15  Strong bearish alignment
        -10  Moderate bearish alignment
        -5   Weak bearish alignment
        -10  Price below all EMAs
        -10  All EMAs sloping down
        -15  Death cross detected
        -8   EMA9/21 bearish cross
        -10  EMA21/50 bearish cross
        -10  Bounce down from EMA resistance
        -5   EMAs diverging downward

        SPECIAL:
        -5   Overextended (might reverse)
        ±0   Tangled EMAs → dampen score toward 50

        Score clamped to 0-100.

        Args:
            df (DataFrame): Price data with 'close' column

        Returns:
            dict: Standard brain result format
        """
        # ------ Default neutral result ------
        neutral_result = {
            "brain": "EMA_CROSSOVER",
            "direction": "NEUTRAL",
            "confidence": 0,
            "current_price": 0.0,
            "ema_values": {
                "ema_9": None,
                "ema_21": None,
                "ema_50": None,
                "ema_100": None,
                "ema_200": None,
            },
            "details": {
                "alignment": {"alignment": "TANGLED",
                              "bullish_count": 0,
                              "bearish_count": 0},
                "crossovers": {"crossovers": [],
                               "golden_cross": False,
                               "death_cross": False,
                               "most_recent": "NONE"},
                "price_position": {"position": "MIXED",
                                   "above_count": 0,
                                   "below_count": 0},
                "slopes": {"overall_slope": "NEUTRAL",
                           "all_rising": False,
                           "all_falling": False},
                "ema_distance": {"spread_condition": "NORMAL",
                                 "overextended": False},
                "bounce": {"bounce_detected": False,
                           "bounced_from": None,
                           "bounce_direction": None,
                           "bounce_strength": 0},
                "trend_strength": "NONE",
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input
            # ============================================
            if df is None or df.empty:
                print("[EMA] ⚠️ No data provided for analysis")
                return neutral_result

            if "close" not in df.columns:
                print("[EMA] ⚠️ 'close' column missing")
                return neutral_result

            if len(df) < self.min_data_points:
                print("[EMA] ⚠️ Need {} rows, got {}".format(
                    self.min_data_points, len(df)
                ))
                return neutral_result

            current_price = float(df["close"].iloc[-1])

            # ============================================
            # STEP 2: Calculate all EMAs
            # ============================================
            emas = self.calculate_all_emas(df)

            if emas is None:
                print("[EMA] ⚠️ EMA calculation failed")
                return neutral_result

            # Extract latest EMA values for result
            ema_values = {}
            for period in self.ema_periods:
                key = "ema_{}".format(period)
                series = emas.get(key)
                if series is not None:
                    valid = series.dropna()
                    ema_values[key] = round(float(valid.iloc[-1]), 6) \
                        if len(valid) > 0 else None
                else:
                    ema_values[key] = None

            # ============================================
            # STEP 3: Run all sub-analyses
            # ============================================

            # 3a: EMA alignment
            alignment = self.check_ema_alignment(emas)

            # 3b: Crossovers
            crossovers = self.detect_crossovers(emas, lookback=5)

            # 3c: Price position
            price_pos = self.check_price_position(df, emas)

            # 3d: Slopes
            slopes = self.calculate_ema_slopes(emas, lookback=5)

            # 3e: Distances
            distances = self.calculate_ema_distance(emas)

            # 3f: Bounce
            bounce = self.detect_ema_bounce(df, emas)

            # ============================================
            # STEP 4: Calculate composite score
            # ============================================
            score = 50.0

            # ------ ALIGNMENT scoring ------
            align_type = alignment["alignment"]

            if align_type == "PERFECT_BULLISH":
                score += 20.0
                print("[EMA] 📈 +20 pts | PERFECT bullish alignment")
            elif align_type == "STRONG_BULLISH":
                score += 15.0
                print("[EMA] 📈 +15 pts | STRONG bullish alignment")
            elif align_type == "MODERATE_BULLISH":
                score += 10.0
                print("[EMA] 📈 +10 pts | MODERATE bullish alignment")
            elif align_type == "WEAK_BULLISH":
                score += 5.0
                print("[EMA] 📈 + 5 pts | WEAK bullish alignment")

            elif align_type == "PERFECT_BEARISH":
                score -= 20.0
                print("[EMA] 📉 -20 pts | PERFECT bearish alignment")
            elif align_type == "STRONG_BEARISH":
                score -= 15.0
                print("[EMA] 📉 -15 pts | STRONG bearish alignment")
            elif align_type == "MODERATE_BEARISH":
                score -= 10.0
                print("[EMA] 📉 -10 pts | MODERATE bearish alignment")
            elif align_type == "WEAK_BEARISH":
                score -= 5.0
                print("[EMA] 📉 - 5 pts | WEAK bearish alignment")

            # ------ PRICE POSITION scoring ------
            if price_pos["position"] == "ABOVE_ALL":
                score += 10.0
                print("[EMA] 📈 +10 pts | Price ABOVE all EMAs")
            elif price_pos["position"] == "BELOW_ALL":
                score -= 10.0
                print("[EMA] 📉 -10 pts | Price BELOW all EMAs")

            # ------ SLOPE scoring ------
            if slopes["all_rising"]:
                score += 10.0
                print("[EMA] 📈 +10 pts | All EMAs sloping UP")
            elif slopes["all_falling"]:
                score -= 10.0
                print("[EMA] 📉 -10 pts | All EMAs sloping DOWN")

            # ------ CROSSOVER scoring ------
            if crossovers["golden_cross"]:
                score += 15.0
                print("[EMA] 📈 +15 pts | GOLDEN CROSS")
            elif crossovers["death_cross"]:
                score -= 15.0
                print("[EMA] 📉 -15 pts | DEATH CROSS")

            # Individual crossovers
            for cross in crossovers["crossovers"]:
                fast = cross["fast"]
                slow = cross["slow"]
                ctype = cross["type"]

                # Skip 50/200 — already counted as golden/death
                if fast == 50 and slow == 200:
                    continue

                if fast == 9 and slow == 21:
                    if ctype == "BULLISH":
                        score += 8.0
                        print("[EMA] 📈 + 8 pts | EMA9/21 bullish cross")
                    else:
                        score -= 8.0
                        print("[EMA] 📉 - 8 pts | EMA9/21 bearish cross")

                elif fast == 21 and slow == 50:
                    if ctype == "BULLISH":
                        score += 10.0
                        print("[EMA] 📈 +10 pts | EMA21/50 bullish cross")
                    else:
                        score -= 10.0
                        print("[EMA] 📉 -10 pts | EMA21/50 bearish cross")

                elif fast == 50 and slow == 100:
                    if ctype == "BULLISH":
                        score += 8.0
                        print("[EMA] 📈 + 8 pts | EMA50/100 bullish cross")
                    else:
                        score -= 8.0
                        print("[EMA] 📉 - 8 pts | EMA50/100 bearish cross")

            # ------ BOUNCE scoring ------
            if bounce["bounce_detected"]:
                if bounce["bounce_direction"] == "UP":
                    score += 10.0
                    print("[EMA] 📈 +10 pts | Bounce UP from {}".format(
                        bounce["bounced_from"]
                    ))
                elif bounce["bounce_direction"] == "DOWN":
                    score -= 10.0
                    print("[EMA] 📉 -10 pts | Bounce DOWN from {}".format(
                        bounce["bounced_from"]
                    ))

            # ------ DISTANCE scoring ------
            spread = distances["spread_condition"]
            if spread == "WIDE":
                # Strong trend but might be overextended
                if score > 50:
                    score += 5.0
                    print("[EMA] 📈 + 5 pts | EMAs diverging (strong trend)")
                elif score < 50:
                    score -= 5.0
                    print("[EMA] 📉 - 5 pts | EMAs diverging (strong trend)")

            # ------ OVEREXTENDED adjustment ------
            if distances["overextended"]:
                # Reduce score toward 50 slightly
                if score > 55:
                    score -= 5.0
                    print("[EMA] ⚠️  - 5 pts | Overextended (may revert)")
                elif score < 45:
                    score += 5.0
                    print("[EMA] ⚠️  + 5 pts | Overextended (may revert)")

            # ------ TANGLED EMAs adjustment ------
            if align_type == "TANGLED":
                # Dampen score toward 50 (no clear trend)
                score = 50.0 + (score - 50.0) * 0.5
                print("[EMA] ⚠️  EMAs tangled — dampening score "
                      "toward neutral")

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

            confidence = max(0.0, min(100.0, round(confidence, 2)))

            # ============================================
            # STEP 7: Determine trend strength label
            # ============================================
            if confidence >= 60:
                trend_strength = "STRONG"
            elif confidence >= 30:
                trend_strength = "MODERATE"
            elif confidence > 0:
                trend_strength = "WEAK"
            else:
                trend_strength = "NONE"

            # ============================================
            # STEP 8: Build result
            # ============================================
            result = {
                "brain": "EMA_CROSSOVER",
                "direction": direction,
                "confidence": confidence,
                "current_price": round(current_price, 6),
                "ema_values": ema_values,
                "details": {
                    "alignment": alignment,
                    "crossovers": crossovers,
                    "price_position": price_pos,
                    "slopes": slopes,
                    "ema_distance": distances,
                    "bounce": bounce,
                    "trend_strength": trend_strength,
                },
            }

            self.results = result

            # ============================================
            # STEP 9: Log summary
            # ============================================
            print("\n[EMA] ═══════════════════════════════════")
            print("[EMA]  EMA Crossover Analysis Complete")
            print("[EMA]  Price        : {:.4f}".format(current_price))

            for period in self.ema_periods:
                key = "ema_{}".format(period)
                val = ema_values.get(key)
                if val is not None:
                    print("[EMA]  EMA {:>3}      : {:.4f}".format(
                        period, val
                    ))
                else:
                    print("[EMA]  EMA {:>3}      : N/A".format(period))

            print("[EMA]  Alignment    : {}".format(align_type))
            print("[EMA]  Price Pos    : {}".format(
                price_pos["position"]
            ))
            print("[EMA]  Slopes       : {}".format(
                slopes["overall_slope"]
            ))
            print("[EMA]  Spread       : {}".format(
                distances["spread_condition"]
            ))

            if crossovers["golden_cross"]:
                print("[EMA]  ⭐ GOLDEN CROSS active")
            if crossovers["death_cross"]:
                print("[EMA]  💀 DEATH CROSS active")
            if bounce["bounce_detected"]:
                print("[EMA]  Bounce       : {} from {}".format(
                    bounce["bounce_direction"],
                    bounce["bounced_from"]
                ))

            print("[EMA]  Trend        : {}".format(trend_strength))
            print("[EMA]  Raw Score    : {:.1f}/100".format(score))
            print("[EMA]  Direction    : {}".format(direction))
            print("[EMA]  Confidence   : {:.1f}%".format(confidence))
            print("[EMA] ═══════════════════════════════════\n")

            return result

        except Exception as e:
            print("[EMA] ❌ Analysis error: {}".format(e))
            return neutral_result


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

ema_crossover_analyzer = EMACrossoverAnalyzer()

print("[EMA] ✅ EMA Crossover module loaded and ready")