# ============================================
# CRYPTO SIGNAL BOT - STOCHASTIC RSI ANALYZER
# ============================================
# Brain: Stochastic RSI (Early Momentum)
#
# StochRSI = Stochastic oscillator applied to
# RSI values instead of price. It catches
# momentum shifts EARLIER than regular RSI.
#
# WHY STOCHRSI MATTERS:
#   - RSI detects overbought/oversold at 70/30
#   - StochRSI detects the SAME conditions at
#     80/20 but FASTER — it leads RSI by 1-3
#     candles on reversals
#   - Catches early momentum shifts before
#     price fully commits to a direction
#   - K/D crossovers signal entry timing
#
# COMPONENTS:
#   RSI = standard RSI(14)
#   StochRSI = (RSI - RSI_low) / (RSI_high - RSI_low)
#   %K = SMA(StochRSI, 3) — fast signal line
#   %D = SMA(%K, 3) — slow signal line
#
# SIGNALS:
#   %K crosses above %D below 20 → STRONG BUY
#   %K crosses below %D above 80 → STRONG SELL
#   %K > %D in neutral zone → mild bullish
#   %K < %D in neutral zone → mild bearish
#   Both below 20 → oversold (reversal expected)
#   Both above 80 → overbought (reversal expected)
#
# SCORING (base=50, 7 factors):
#   Factor 1: K/D crossover            ±15
#   Factor 2: Extreme zone position    ±12
#   Factor 3: K/D relationship         ±5
#   Factor 4: StochRSI trend           ±8
#   Factor 5: Zone exit detection      ±10
#   Factor 6: Regular RSI alignment    ±7
#   Factor 7: Confluence bonus         ±5
#   Range: 0 to 100 (clamped)
#
# Usage:
#   from algorithms.stochastic_rsi import stochrsi_analyzer
#   result = stochrsi_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class StochRSIAnalyzer:
    """
    Stochastic RSI analyzer for early momentum detection.

    Calculates RSI, then applies Stochastic oscillator
    to RSI values. Detects K/D crossovers, extreme zones,
    zone exits, and trend direction.

    All calculations from scratch. No external libraries.

    Attributes:
        rsi_period (int):       RSI calculation period (14)
        stoch_period (int):     Stochastic lookback (14)
        k_period (int):         %K smoothing period (3)
        d_period (int):         %D smoothing period (3)
        overbought (float):     Upper threshold (80)
        oversold (float):       Lower threshold (20)
        min_data_points (int):  Minimum candles needed
    """

    # ============================================
    # SCORING CONSTANTS
    # ============================================

    POINTS = {
        "crossover": 15.0,
        "extreme_zone": 12.0,
        "kd_relationship": 5.0,
        "trend": 8.0,
        "zone_exit": 10.0,
        "rsi_alignment": 7.0,
        "confluence": 5.0,
    }

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize Stochastic RSI Analyzer.

        Parameters:
        - rsi_period=14: standard RSI lookback
        - stoch_period=14: stochastic lookback on RSI
        - k_period=3: %K smoothing (fast line)
        - d_period=3: %D smoothing (slow line)
        - overbought=80: upper extreme zone
        - oversold=20: lower extreme zone
        - min_data_points=35: RSI(14) + Stoch(14) + buffer
        """
        self.rsi_period = Config.RSI_PERIOD
        self.stoch_period = 14
        self.k_period = 3
        self.d_period = 3
        self.overbought = 80.0
        self.oversold = 20.0

        # Need: rsi_period + stoch_period + k + d + buffer
        self.min_data_points = (
            self.rsi_period + self.stoch_period + 5
        )

        # Result storage
        self.results = {}

        print("[STOCHRSI] ✅ Analyzer initialized | "
              "RSI: {} | Stoch: {} | K: {} | D: {} | "
              "OB: {} | OS: {}".format(
                  self.rsi_period, self.stoch_period,
                  self.k_period, self.d_period,
                  self.overbought, self.oversold,
              ))

    # ============================================
    # FUNCTION 2: CALCULATE RSI (From Scratch)
    # ============================================

    def _calculate_rsi(self, closes):
        """
        Calculate RSI using Wilder's smoothing.

        Same algorithm as rsi.py brain but returns
        numpy array instead of pandas Series for
        internal use.

        Args:
            closes (numpy array): Close prices

        Returns:
            numpy array: RSI values (NaN for first
                        'period' entries)
        """
        try:
            n = len(closes)
            period = self.rsi_period

            if n < period + 1:
                return np.full(n, np.nan)

            # Price changes
            deltas = np.diff(closes)

            # Separate gains and losses
            gains = np.where(deltas > 0, deltas, 0.0)
            losses = np.where(deltas < 0, -deltas, 0.0)

            # First average (SMA)
            first_avg_gain = np.mean(gains[:period])
            first_avg_loss = np.mean(losses[:period])

            # Wilder's smoothing
            avg_gain = np.zeros(n - 1)
            avg_loss = np.zeros(n - 1)

            avg_gain[period - 1] = first_avg_gain
            avg_loss[period - 1] = first_avg_loss

            for i in range(period, n - 1):
                avg_gain[i] = (
                    (avg_gain[i - 1] * (period - 1)
                     + gains[i])
                    / period
                )
                avg_loss[i] = (
                    (avg_loss[i - 1] * (period - 1)
                     + losses[i])
                    / period
                )

            # RSI calculation
            rsi = np.full(n, np.nan)

            for i in range(period, n):
                idx = i - 1  # index into avg arrays

                if avg_loss[idx] == 0:
                    rsi[i] = 100.0
                elif avg_gain[idx] == 0:
                    rsi[i] = 0.0
                else:
                    rs = avg_gain[idx] / avg_loss[idx]
                    rsi[i] = 100.0 - (100.0 / (1.0 + rs))

            return rsi

        except Exception as e:
            print("[STOCHRSI] ❌ RSI calc error: "
                  "{}".format(e))
            return np.full(len(closes), np.nan)

    # ============================================
    # FUNCTION 3: CALCULATE STOCHASTIC RSI
    # ============================================

    def calculate_stoch_rsi(self, df):
        """
        Calculate Stochastic RSI with %K and %D.

        Steps:
        1. Calculate RSI(14)
        2. For each point, find RSI min/max over
           last stoch_period candles
        3. StochRSI = (RSI - RSI_min) / (RSI_max - RSI_min)
           Scaled to 0-100
        4. %K = SMA(StochRSI, k_period)
        5. %D = SMA(%K, d_period)

        Args:
            df (DataFrame): Must have 'close' column

        Returns:
            dict: {
                "stoch_rsi": numpy array,
                "k_line": numpy array,
                "d_line": numpy array,
                "rsi": numpy array
            }
            Returns None on error.
        """
        try:
            if df is None or df.empty:
                print("[STOCHRSI] ⚠️ Empty DataFrame")
                return None

            if "close" not in df.columns:
                print("[STOCHRSI] ⚠️ 'close' missing")
                return None

            closes = df["close"].astype(float).values
            n = len(closes)

            if n < self.min_data_points:
                print("[STOCHRSI] ⚠️ Need {} rows, "
                      "got {}".format(
                          self.min_data_points, n
                      ))
                return None

            # ── Step 1: Calculate RSI ──
            rsi = self._calculate_rsi(closes)

            # ── Step 2-3: Stochastic of RSI ──
            stoch_rsi = np.full(n, np.nan)

            for i in range(
                self.rsi_period + self.stoch_period,
                n
            ):
                # Get RSI window
                window = rsi[
                    i - self.stoch_period + 1: i + 1
                ]

                # Remove NaN from window
                valid = window[~np.isnan(window)]

                if len(valid) < 2:
                    continue

                rsi_min = np.min(valid)
                rsi_max = np.max(valid)
                rsi_range = rsi_max - rsi_min

                if rsi_range == 0:
                    stoch_rsi[i] = 50.0
                else:
                    stoch_rsi[i] = (
                        (rsi[i] - rsi_min) / rsi_range
                    ) * 100.0

            # ── Step 4: %K = SMA of StochRSI ──
            k_line = np.full(n, np.nan)

            for i in range(
                self.k_period - 1, n
            ):
                window = stoch_rsi[
                    i - self.k_period + 1: i + 1
                ]
                valid = window[~np.isnan(window)]

                if len(valid) == self.k_period:
                    k_line[i] = np.mean(valid)

            # ── Step 5: %D = SMA of %K ──
            d_line = np.full(n, np.nan)

            for i in range(
                self.d_period - 1, n
            ):
                window = k_line[
                    i - self.d_period + 1: i + 1
                ]
                valid = window[~np.isnan(window)]

                if len(valid) == self.d_period:
                    d_line[i] = np.mean(valid)

            # Count valid values
            valid_k = int(np.sum(~np.isnan(k_line)))
            valid_d = int(np.sum(~np.isnan(d_line)))

            if valid_k > 0 and valid_d > 0:
                print("[STOCHRSI] Calculated | "
                      "K: {} valid | D: {} valid | "
                      "K={:.1f} D={:.1f}".format(
                          valid_k, valid_d,
                          k_line[~np.isnan(k_line)][-1],
                          d_line[~np.isnan(d_line)][-1],
                      ))

            return {
                "stoch_rsi": stoch_rsi,
                "k_line": k_line,
                "d_line": d_line,
                "rsi": rsi,
            }

        except Exception as e:
            print("[STOCHRSI] ❌ StochRSI calc error: "
                  "{}".format(e))
            return None

    # ============================================
    # FUNCTION 4: DETECT K/D CROSSOVER
    # ============================================

    def detect_crossover(self, k_line, d_line):
        """
        Detect %K crossing %D in last 3 candles.

        BULLISH CROSS: %K crosses above %D
          - Below 20: STRONG bullish (oversold cross)
          - 20-80: MILD bullish
          - Above 80: WEAK (already overbought)

        BEARISH CROSS: %K crosses below %D
          - Above 80: STRONG bearish (overbought cross)
          - 20-80: MILD bearish
          - Below 20: WEAK (already oversold)

        Args:
            k_line (numpy array): %K values
            d_line (numpy array): %D values

        Returns:
            dict: {
                "crossover": "BULLISH"/"BEARISH"/"NONE",
                "zone": "OVERSOLD"/"OVERBOUGHT"/"NEUTRAL",
                "strength": "STRONG"/"MILD"/"WEAK"
            }
        """
        default = {
            "crossover": "NONE",
            "zone": "NEUTRAL",
            "strength": "WEAK",
        }

        try:
            n = len(k_line)

            if n < 3:
                return default

            # Check last 3 candles
            for i in range(-1, -3, -1):
                prev_idx = i - 1

                if abs(prev_idx) > n:
                    break

                prev_k = k_line[prev_idx]
                curr_k = k_line[i]
                prev_d = d_line[prev_idx]
                curr_d = d_line[i]

                # Skip NaN
                if (np.isnan(prev_k) or
                        np.isnan(curr_k) or
                        np.isnan(prev_d) or
                        np.isnan(curr_d)):
                    continue

                # Determine zone
                avg_level = (curr_k + curr_d) / 2.0

                if avg_level < self.oversold:
                    zone = "OVERSOLD"
                elif avg_level > self.overbought:
                    zone = "OVERBOUGHT"
                else:
                    zone = "NEUTRAL"

                # BULLISH: K was below D, now above
                if prev_k < prev_d and curr_k >= curr_d:
                    if zone == "OVERSOLD":
                        strength = "STRONG"
                    elif zone == "NEUTRAL":
                        strength = "MILD"
                    else:
                        strength = "WEAK"

                    print("[STOCHRSI] ↗️ BULLISH cross "
                          "in {} zone ({})"
                          .format(zone, strength))

                    return {
                        "crossover": "BULLISH",
                        "zone": zone,
                        "strength": strength,
                    }

                # BEARISH: K was above D, now below
                if prev_k > prev_d and curr_k <= curr_d:
                    if zone == "OVERBOUGHT":
                        strength = "STRONG"
                    elif zone == "NEUTRAL":
                        strength = "MILD"
                    else:
                        strength = "WEAK"

                    print("[STOCHRSI] ↘️ BEARISH cross "
                          "in {} zone ({})"
                          .format(zone, strength))

                    return {
                        "crossover": "BEARISH",
                        "zone": zone,
                        "strength": strength,
                    }

            return default

        except Exception as e:
            print("[STOCHRSI] ❌ Crossover error: "
                  "{}".format(e))
            return default
    # ============================================
    # FUNCTION 5: DETECT ZONE EXIT
    # ============================================

    def detect_zone_exit(self, k_line):
        """
        Detect %K leaving extreme zones.

        EXIT OVERSOLD: %K was below 20, now above 20
          → momentum shifting bullish
        EXIT OVERBOUGHT: %K was above 80, now below 80
          → momentum shifting bearish

        This catches the MOMENT momentum changes,
        which is earlier than waiting for a crossover.

        Args:
            k_line (numpy array): %K values

        Returns:
            str: "EXIT_OVERSOLD", "EXIT_OVERBOUGHT",
                 or "NONE"
        """
        try:
            n = len(k_line)

            if n < 3:
                return "NONE"

            # Check last 3 candles for zone exit
            for i in range(-1, -3, -1):
                prev_idx = i - 1

                if abs(prev_idx) > n:
                    break

                prev_k = k_line[prev_idx]
                curr_k = k_line[i]

                if np.isnan(prev_k) or np.isnan(curr_k):
                    continue

                # Was below 20, now above 20
                if (prev_k < self.oversold and
                        curr_k >= self.oversold):
                    print("[STOCHRSI] 🔼 EXIT OVERSOLD "
                          "({:.1f} → {:.1f})".format(
                              prev_k, curr_k
                          ))
                    return "EXIT_OVERSOLD"

                # Was above 80, now below 80
                if (prev_k > self.overbought and
                        curr_k <= self.overbought):
                    print("[STOCHRSI] 🔽 EXIT OVERBOUGHT "
                          "({:.1f} → {:.1f})".format(
                              prev_k, curr_k
                          ))
                    return "EXIT_OVERBOUGHT"

            return "NONE"

        except Exception as e:
            print("[STOCHRSI] ❌ Zone exit error: "
                  "{}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 6: GET STOCHRSI TREND
    # ============================================

    def get_trend(self, k_line, lookback=5):
        """
        Determine %K trend direction.

        Uses net change + consistency check over
        last 'lookback' valid K values.

        RISING:  %K trending up = bullish momentum
        FALLING: %K trending down = bearish momentum
        FLAT:    %K sideways = no clear momentum

        Args:
            k_line (numpy array): %K values
            lookback (int): How many candles to check

        Returns:
            str: "RISING", "FALLING", or "FLAT"
        """
        try:
            # Get last valid K values
            valid_indices = np.where(
                ~np.isnan(k_line)
            )[0]

            if len(valid_indices) < 3:
                return "FLAT"

            actual_lookback = min(
                lookback, len(valid_indices)
            )
            recent_indices = valid_indices[
                -actual_lookback:
            ]
            recent_k = k_line[recent_indices]

            # Net change
            net_change = recent_k[-1] - recent_k[0]

            # Consistency
            diffs = np.diff(recent_k)

            if len(diffs) == 0:
                return "FLAT"

            rising = int(np.sum(diffs > 0))
            falling = int(np.sum(diffs < 0))
            total = len(diffs)

            # Need net change > 3 points AND
            # 60%+ consistency
            if (net_change > 3.0 and
                    rising >= total * 0.6):
                return "RISING"

            if (net_change < -3.0 and
                    falling >= total * 0.6):
                return "FALLING"

            return "FLAT"

        except Exception as e:
            print("[STOCHRSI] ❌ Trend error: "
                  "{}".format(e))
            return "FLAT"

    # ============================================
    # FUNCTION 7: CHECK RSI ALIGNMENT
    # ============================================

    def check_rsi_alignment(self, rsi_values,
                             stochrsi_direction):
        """
        Check if regular RSI agrees with StochRSI.

        When both RSI and StochRSI agree on direction,
        the signal is much stronger. When they disagree,
        it's a warning sign.

        ALIGNED_BULLISH:
          StochRSI says LONG + RSI > 50 (bullish territory)
        ALIGNED_BEARISH:
          StochRSI says SHORT + RSI < 50 (bearish territory)
        DIVERGENT:
          StochRSI and RSI disagree
        NEUTRAL:
          Can't determine

        Args:
            rsi_values (numpy array): RSI values
            stochrsi_direction (str): "LONG" or "SHORT"

        Returns:
            str: "ALIGNED_BULLISH", "ALIGNED_BEARISH",
                 "DIVERGENT", or "NEUTRAL"
        """
        try:
            if rsi_values is None:
                return "NEUTRAL"

            # Get latest valid RSI
            valid_rsi = rsi_values[
                ~np.isnan(rsi_values)
            ]

            if len(valid_rsi) == 0:
                return "NEUTRAL"

            current_rsi = float(valid_rsi[-1])

            # RSI territory
            rsi_bullish = current_rsi > 50
            rsi_bearish = current_rsi < 50

            # Check alignment
            if stochrsi_direction == "LONG":
                if rsi_bullish:
                    return "ALIGNED_BULLISH"
                elif rsi_bearish:
                    return "DIVERGENT"

            elif stochrsi_direction == "SHORT":
                if rsi_bearish:
                    return "ALIGNED_BEARISH"
                elif rsi_bullish:
                    return "DIVERGENT"

            return "NEUTRAL"

        except Exception as e:
            print("[STOCHRSI] ❌ RSI alignment "
                  "error: {}".format(e))
            return "NEUTRAL"

    # ============================================
    # FUNCTION 8: GET CURRENT ZONE
    # ============================================

    def get_current_zone(self, k_value, d_value):
        """
        Classify where %K and %D are right now.

        EXTREME_OVERSOLD: both below 10
        OVERSOLD: both below 20
        EXTREME_OVERBOUGHT: both above 90
        OVERBOUGHT: both above 80
        NEUTRAL_BULLISH: K > 50 and K > D
        NEUTRAL_BEARISH: K < 50 and K < D
        NEUTRAL: everything else

        Args:
            k_value (float): Current %K
            d_value (float): Current %D

        Returns:
            str: Zone classification
        """
        try:
            if (np.isnan(k_value) or
                    np.isnan(d_value)):
                return "NEUTRAL"

            # Extreme zones first
            if k_value < 10 and d_value < 10:
                return "EXTREME_OVERSOLD"

            if k_value > 90 and d_value > 90:
                return "EXTREME_OVERBOUGHT"

            if k_value < self.oversold and \
                    d_value < self.oversold:
                return "OVERSOLD"

            if k_value > self.overbought and \
                    d_value > self.overbought:
                return "OVERBOUGHT"

            # Neutral sub-zones
            if k_value > 50 and k_value > d_value:
                return "NEUTRAL_BULLISH"

            if k_value < 50 and k_value < d_value:
                return "NEUTRAL_BEARISH"

            return "NEUTRAL"

        except Exception as e:
            print("[STOCHRSI] ❌ Zone error: "
                  "{}".format(e))
            return "NEUTRAL"
    # ============================================
    # FUNCTION 9: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        MAIN ANALYSIS FUNCTION — Runs all StochRSI
        checks and produces a scored trading signal.

        Pipeline:
        1. Calculate StochRSI (%K, %D, RSI)
        2. Get current zone
        3. Detect K/D crossover
        4. Detect zone exit
        5. Get StochRSI trend
        6. Check RSI alignment
        7. Score all factors
        8. Direction and confidence

        SCORING:
        Base = 50 (neutral)
        Factor 1: K/D crossover              ±15
        Factor 2: Extreme zone position       ±12
        Factor 3: K/D relationship            ±5
        Factor 4: StochRSI trend              ±8
        Factor 5: Zone exit                   ±10
        Factor 6: RSI alignment               ±7
        Factor 7: Confluence (4+ agree)       ±5

        Args:
            df (DataFrame): OHLCV data

        Returns:
            dict: Standard brain result format
        """
        neutral_result = {
            "brain": "STOCHASTIC_RSI",
            "direction": "NEUTRAL",
            "confidence": 0,
            "k_value": 50.0,
            "d_value": 50.0,
            "rsi_value": 50.0,
            "details": {
                "zone": "NEUTRAL",
                "crossover": "NONE",
                "crossover_strength": "WEAK",
                "crossover_zone": "NEUTRAL",
                "zone_exit": "NONE",
                "trend": "FLAT",
                "rsi_alignment": "NEUTRAL",
                "bullish_factors": 0,
                "bearish_factors": 0,
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input
            # ============================================
            if df is None or df.empty:
                print("[STOCHRSI] ⚠️ No data provided")
                return neutral_result

            if "close" not in df.columns:
                print("[STOCHRSI] ⚠️ 'close' missing")
                return neutral_result

            if len(df) < self.min_data_points:
                print("[STOCHRSI] ⚠️ Need {} rows, "
                      "got {}".format(
                          self.min_data_points,
                          len(df),
                      ))
                return neutral_result

            # ============================================
            # STEP 2: Calculate StochRSI
            # ============================================
            stoch_data = self.calculate_stoch_rsi(df)

            if stoch_data is None:
                print("[STOCHRSI] ⚠️ Calculation failed")
                return neutral_result

            k_line = stoch_data["k_line"]
            d_line = stoch_data["d_line"]
            rsi = stoch_data["rsi"]

            # Get latest valid values
            valid_k = k_line[~np.isnan(k_line)]
            valid_d = d_line[~np.isnan(d_line)]
            valid_rsi = rsi[~np.isnan(rsi)]

            if len(valid_k) == 0 or len(valid_d) == 0:
                print("[STOCHRSI] ⚠️ No valid K/D values")
                return neutral_result

            current_k = float(valid_k[-1])
            current_d = float(valid_d[-1])
            current_rsi = (
                float(valid_rsi[-1])
                if len(valid_rsi) > 0
                else 50.0
            )

            # ============================================
            # STEP 3: Run all sub-analyses
            # ============================================

            # 3a: Current zone
            zone = self.get_current_zone(
                current_k, current_d
            )

            # 3b: K/D crossover
            crossover_data = self.detect_crossover(
                k_line, d_line
            )
            crossover = crossover_data["crossover"]
            cross_zone = crossover_data["zone"]
            cross_strength = crossover_data["strength"]

            # 3c: Zone exit
            zone_exit = self.detect_zone_exit(k_line)

            # 3d: Trend
            trend = self.get_trend(k_line, lookback=5)

            # ============================================
            # STEP 4: SCORING
            # ============================================
            score = 50.0
            bullish_factors = 0
            bearish_factors = 0

            # ── Factor 1: K/D Crossover (±15) ──
            # Strongest signal — especially in
            # extreme zones
            if crossover == "BULLISH":
                pts = self.POINTS["crossover"]

                # Strong cross in oversold = full points
                # Mild cross in neutral = 60% points
                # Weak cross in overbought = 30% points
                if cross_strength == "STRONG":
                    score += pts
                elif cross_strength == "MILD":
                    score += pts * 0.6
                else:
                    score += pts * 0.3

                bullish_factors += 1
                print("[STOCHRSI] 📈 +{:.0f} pts | "
                      "BULLISH cross ({} in {})".format(
                          pts if cross_strength == "STRONG"
                          else pts * 0.6
                          if cross_strength == "MILD"
                          else pts * 0.3,
                          cross_strength,
                          cross_zone,
                      ))

            elif crossover == "BEARISH":
                pts = self.POINTS["crossover"]

                if cross_strength == "STRONG":
                    score -= pts
                elif cross_strength == "MILD":
                    score -= pts * 0.6
                else:
                    score -= pts * 0.3

                bearish_factors += 1
                print("[STOCHRSI] 📉 -{:.0f} pts | "
                      "BEARISH cross ({} in {})".format(
                          pts if cross_strength == "STRONG"
                          else pts * 0.6
                          if cross_strength == "MILD"
                          else pts * 0.3,
                          cross_strength,
                          cross_zone,
                      ))

            # ── Factor 2: Extreme Zone (±12) ──
            # Being in extreme zone = reversal likely
            if zone == "EXTREME_OVERSOLD":
                score += self.POINTS["extreme_zone"]
                bullish_factors += 1
                print("[STOCHRSI] 📈 +{:.0f} pts | "
                      "EXTREME OVERSOLD (K={:.1f} "
                      "D={:.1f})".format(
                          self.POINTS["extreme_zone"],
                          current_k, current_d,
                      ))

            elif zone == "OVERSOLD":
                score += self.POINTS["extreme_zone"] * 0.7
                bullish_factors += 1
                print("[STOCHRSI] 📈 +{:.0f} pts | "
                      "OVERSOLD".format(
                          self.POINTS["extreme_zone"] * 0.7
                      ))

            elif zone == "EXTREME_OVERBOUGHT":
                score -= self.POINTS["extreme_zone"]
                bearish_factors += 1
                print("[STOCHRSI] 📉 -{:.0f} pts | "
                      "EXTREME OVERBOUGHT (K={:.1f} "
                      "D={:.1f})".format(
                          self.POINTS["extreme_zone"],
                          current_k, current_d,
                      ))

            elif zone == "OVERBOUGHT":
                score -= self.POINTS["extreme_zone"] * 0.7
                bearish_factors += 1
                print("[STOCHRSI] 📉 -{:.0f} pts | "
                      "OVERBOUGHT".format(
                          self.POINTS["extreme_zone"] * 0.7
                      ))

            # ── Factor 3: K/D Relationship (±5) ──
            if current_k > current_d + 2:
                score += self.POINTS["kd_relationship"]
                bullish_factors += 1
                print("[STOCHRSI] 📈 +{:.0f} pts | "
                      "K above D".format(
                          self.POINTS["kd_relationship"]
                      ))

            elif current_k < current_d - 2:
                score -= self.POINTS["kd_relationship"]
                bearish_factors += 1
                print("[STOCHRSI] 📉 -{:.0f} pts | "
                      "K below D".format(
                          self.POINTS["kd_relationship"]
                      ))

            # ── Factor 4: Trend (±8) ──
            if trend == "RISING":
                score += self.POINTS["trend"]
                bullish_factors += 1
                print("[STOCHRSI] 📈 +{:.0f} pts | "
                      "Trend RISING".format(
                          self.POINTS["trend"]
                      ))

            elif trend == "FALLING":
                score -= self.POINTS["trend"]
                bearish_factors += 1
                print("[STOCHRSI] 📉 -{:.0f} pts | "
                      "Trend FALLING".format(
                          self.POINTS["trend"]
                      ))

            # ── Factor 5: Zone Exit (±10) ──
            if zone_exit == "EXIT_OVERSOLD":
                score += self.POINTS["zone_exit"]
                bullish_factors += 1
                print("[STOCHRSI] 📈 +{:.0f} pts | "
                      "EXIT oversold zone".format(
                          self.POINTS["zone_exit"]
                      ))

            elif zone_exit == "EXIT_OVERBOUGHT":
                score -= self.POINTS["zone_exit"]
                bearish_factors += 1
                print("[STOCHRSI] 📉 -{:.0f} pts | "
                      "EXIT overbought zone".format(
                          self.POINTS["zone_exit"]
                      ))

            # ── Factor 6: RSI Alignment (±7) ──
            if score > 52:
                prelim_dir = "LONG"
            elif score < 48:
                prelim_dir = "SHORT"
            else:
                prelim_dir = "NEUTRAL"

            rsi_align = self.check_rsi_alignment(
                rsi, prelim_dir
            )

            if rsi_align == "ALIGNED_BULLISH":
                score += self.POINTS["rsi_alignment"]
                bullish_factors += 1
                print("[STOCHRSI] 📈 +{:.0f} pts | "
                      "RSI aligned bullish "
                      "(RSI={:.1f})".format(
                          self.POINTS["rsi_alignment"],
                          current_rsi,
                      ))

            elif rsi_align == "ALIGNED_BEARISH":
                score -= self.POINTS["rsi_alignment"]
                bearish_factors += 1
                print("[STOCHRSI] 📉 -{:.0f} pts | "
                      "RSI aligned bearish "
                      "(RSI={:.1f})".format(
                          self.POINTS["rsi_alignment"],
                          current_rsi,
                      ))

            elif rsi_align == "DIVERGENT":
                if score > 55:
                    score -= 4.0
                    print("[STOCHRSI] ⚠️ -4 pts | RSI "
                          "divergent (dampening)")
                elif score < 45:
                    score += 4.0
                    print("[STOCHRSI] ⚠️ +4 pts | RSI "
                          "divergent (dampening)")

            # ── Factor 7: Confluence (±5) ──
            if bullish_factors >= 4:
                score += self.POINTS["confluence"]
                print("[STOCHRSI] 📈 +{:.0f} pts | "
                      "Confluence ({} bullish "
                      "factors)".format(
                          self.POINTS["confluence"],
                          bullish_factors,
                      ))

            elif bearish_factors >= 4:
                score -= self.POINTS["confluence"]
                print("[STOCHRSI] 📉 -{:.0f} pts | "
                      "Confluence ({} bearish "
                      "factors)".format(
                          self.POINTS["confluence"],
                          bearish_factors,
                      ))

            # ── Clamp score ──
            score = max(0.0, min(100.0, score))

            # ============================================
            # STEP 5: Direction and Confidence
            # ============================================
            if score > 55:
                direction = "LONG"
                confidence = min(
                    100.0, (score - 50.0) * 2.0
                )
            elif score < 45:
                direction = "SHORT"
                confidence = min(
                    100.0, (50.0 - score) * 2.0
                )
            else:
                direction = "NEUTRAL"
                confidence = 0.0

            confidence = round(confidence, 2)

            # ============================================
            # STEP 6: Build result
            # ============================================
            result = {
                "brain": "STOCHASTIC_RSI",
                "direction": direction,
                "confidence": confidence,
                "k_value": round(current_k, 2),
                "d_value": round(current_d, 2),
                "rsi_value": round(current_rsi, 2),
                "details": {
                    "zone": zone,
                    "crossover": crossover,
                    "crossover_strength": cross_strength,
                    "crossover_zone": cross_zone,
                    "zone_exit": zone_exit,
                    "trend": trend,
                    "rsi_alignment": rsi_align,
                    "bullish_factors": bullish_factors,
                    "bearish_factors": bearish_factors,
                },
            }

            self.results = result

            # ============================================
            # STEP 7: Log summary
            # ============================================
            print("\n[STOCHRSI] ══════════════════════"
                  "══════════════")
            print("[STOCHRSI]  Stochastic RSI Analysis")
            print("[STOCHRSI]  %K          : {:.2f}"
                  .format(current_k))
            print("[STOCHRSI]  %D          : {:.2f}"
                  .format(current_d))
            print("[STOCHRSI]  RSI         : {:.2f}"
                  .format(current_rsi))
            print("[STOCHRSI]  Zone        : {}"
                  .format(zone))
            print("[STOCHRSI]  Crossover   : {} ({} "
                  "in {})".format(
                      crossover, cross_strength,
                      cross_zone,
                  ))
            print("[STOCHRSI]  Zone Exit   : {}"
                  .format(zone_exit))
            print("[STOCHRSI]  Trend       : {}"
                  .format(trend))
            print("[STOCHRSI]  RSI Align   : {}"
                  .format(rsi_align))
            print("[STOCHRSI]  Bull/Bear   : {}/{}"
                  .format(
                      bullish_factors,
                      bearish_factors,
                  ))
            print("[STOCHRSI]  Score       : {:.1f}/100"
                  .format(score))
            print("[STOCHRSI]  Direction   : {}"
                  .format(direction))
            print("[STOCHRSI]  Confidence  : {:.1f}%"
                  .format(confidence))
            print("[STOCHRSI] ══════════════════════"
                  "══════════════\n")

            return result

        except Exception as e:
            print("[STOCHRSI] ❌ Analysis error: "
                  "{}".format(e))
            return neutral_result


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

stochrsi_analyzer = StochRSIAnalyzer()

print("[STOCHRSI] ✅ Stochastic RSI module loaded "
      "and ready")
                                      