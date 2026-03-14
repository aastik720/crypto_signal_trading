# ============================================
# CRYPTO SIGNAL BOT - VWAP ANALYZER
# ============================================
# Brain: VWAP (Volume Weighted Average Price)
#
# VWAP = the average price weighted by volume.
# It shows where SMART MONEY transacted.
#
# WHY VWAP MATTERS:
#   - Institutional traders use VWAP as benchmark
#   - Price above VWAP = buyers in control
#   - Price below VWAP = sellers in control
#   - VWAP acts as dynamic support/resistance
#   - Distance from VWAP shows overextension
#
# SIGNALS:
#   Price crosses above VWAP → bullish
#   Price crosses below VWAP → bearish
#   Price bounces off VWAP   → trend continuation
#   Price far from VWAP      → mean reversion likely
#
# SCORING (base=50, 7 factors):
#   Factor 1: Price vs VWAP position     ±10
#   Factor 2: VWAP crossover             ±12
#   Factor 3: VWAP bounce                ±10
#   Factor 4: Distance (overextension)   ±8
#   Factor 5: VWAP slope (trend)         ±8
#   Factor 6: Volume confirmation        ±7
#   Factor 7: Confluence bonus           ±5
#   Range: 0 to 100 (clamped)
#
# Usage:
#   from algorithms.vwap import vwap_analyzer
#   result = vwap_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class VWAPAnalyzer:
    """
    Volume Weighted Average Price analyzer.

    Calculates VWAP from OHLCV data and detects:
    - Price position relative to VWAP
    - VWAP crossovers (bullish/bearish)
    - VWAP bounces (support/resistance)
    - Overextension from VWAP
    - VWAP trend direction
    - Volume confirmation

    All calculations from scratch. No external
    libraries for indicators.

    Attributes:
        slope_period (int):     Candles for slope calc
        bounce_tolerance (float): % tolerance for bounce
        overextend_threshold (float): % for overextension
        min_data_points (int):  Minimum candles needed
    """

    # ============================================
    # SCORING CONSTANTS
    # ============================================

    POINTS = {
        "position": 10.0,
        "crossover": 12.0,
        "bounce": 10.0,
        "distance": 8.0,
        "slope": 8.0,
        "volume": 7.0,
        "confluence": 5.0,
    }

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize VWAP Analyzer.

        Parameters tuned for 5-minute crypto candles:
        - slope_period=5: ~25 minutes for VWAP direction
        - bounce_tolerance=0.3%: how close = "touching"
        - overextend_threshold=1.0%: too far from VWAP
        - min_data_points=20: ~100 minutes minimum
        """
        self.slope_period = 5
        self.bounce_tolerance = 0.3
        self.overextend_threshold = 1.0
        self.min_data_points = 20

        # Result storage
        self.results = {}

        print("[VWAP] ✅ Analyzer initialized | "
              "Slope: {} | Bounce: {}% | "
              "Overextend: {}%".format(
                  self.slope_period,
                  self.bounce_tolerance,
                  self.overextend_threshold,
              ))

    # ============================================
    # FUNCTION 2: CALCULATE VWAP
    # ============================================

    def calculate_vwap(self, df):
        """
        Calculate VWAP from scratch.

        Formula:
            Typical Price = (High + Low + Close) / 3
            VWAP = cumsum(Typical Price × Volume)
                   / cumsum(Volume)

        This gives a running average price weighted
        by volume. High-volume candles pull VWAP
        toward their price more than low-volume ones.

        Args:
            df (DataFrame): Must have high, low, close,
                           volume columns

        Returns:
            pd.Series: VWAP values, or None on error
        """
        try:
            if df is None or df.empty:
                print("[VWAP] ⚠️ Empty DataFrame")
                return None

            required = ["high", "low", "close", "volume"]
            for col in required:
                if col not in df.columns:
                    print("[VWAP] ⚠️ '{}' column "
                          "missing".format(col))
                    return None

            if len(df) < self.min_data_points:
                print("[VWAP] ⚠️ Need {} rows, "
                      "got {}".format(
                          self.min_data_points,
                          len(df),
                      ))
                return None

            high = df["high"].astype(float).values
            low = df["low"].astype(float).values
            close = df["close"].astype(float).values
            volume = df["volume"].astype(float).values

            # Replace zero/NaN volume with tiny value
            # to prevent division by zero
            volume = np.where(
                (volume <= 0) | np.isnan(volume),
                0.0001,
                volume,
            )

            # Typical price
            typical_price = (high + low + close) / 3.0

            # Cumulative sums
            cum_tp_vol = np.cumsum(
                typical_price * volume
            )
            cum_vol = np.cumsum(volume)

            # VWAP = cumulative(TP×V) / cumulative(V)
            vwap_values = cum_tp_vol / cum_vol

            vwap_series = pd.Series(
                vwap_values,
                index=df.index,
                name="VWAP",
                dtype=np.float64,
            )

            current = float(vwap_series.iloc[-1])
            print("[VWAP] Calculated | {} values | "
                  "Current: {:.4f}".format(
                      len(vwap_series), current
                  ))

            return vwap_series

        except Exception as e:
            print("[VWAP] ❌ VWAP calculation error: "
                  "{}".format(e))
            return None

    # ============================================
    # FUNCTION 3: DETECT CROSSOVER
    # ============================================

    def detect_crossover(self, closes, vwap_values):
        """
        Detect price crossing VWAP in last 3 candles.

        BULLISH: price was below VWAP, now above
        BEARISH: price was above VWAP, now below

        Args:
            closes (numpy array): Close prices
            vwap_values (numpy array): VWAP values

        Returns:
            str: "BULLISH", "BEARISH", or "NONE"
        """
        try:
            if len(closes) < 3 or len(vwap_values) < 3:
                return "NONE"

            # Check last 3 candles
            for i in range(-1, -3, -1):
                prev_idx = i - 1

                if abs(prev_idx) > len(closes):
                    break

                prev_close = closes[prev_idx]
                curr_close = closes[i]
                prev_vwap = vwap_values[prev_idx]
                curr_vwap = vwap_values[i]

                if (np.isnan(prev_close) or
                        np.isnan(curr_close) or
                        np.isnan(prev_vwap) or
                        np.isnan(curr_vwap)):
                    continue

                # Below → Above = BULLISH
                if (prev_close < prev_vwap and
                        curr_close >= curr_vwap):
                    print("[VWAP] ↗️ BULLISH crossover")
                    return "BULLISH"

                # Above → Below = BEARISH
                if (prev_close > prev_vwap and
                        curr_close <= curr_vwap):
                    print("[VWAP] ↘️ BEARISH crossover")
                    return "BEARISH"

            return "NONE"

        except Exception as e:
            print("[VWAP] ❌ Crossover error: "
                  "{}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 4: DETECT BOUNCE
    # ============================================

    def detect_bounce(self, df, vwap_series):
        """
        Detect price bouncing off VWAP.

        BOUNCE UP: price dipped near VWAP then
                   recovered above it (bullish)
        BOUNCE DOWN: price rose near VWAP then
                     fell below it (bearish)

        Args:
            df (DataFrame): Must have close, low, high
            vwap_series (pd.Series): VWAP values

        Returns:
            str: "BOUNCE_UP", "BOUNCE_DOWN", or "NONE"
        """
        try:
            if df is None or vwap_series is None:
                return "NONE"

            if len(df) < 5:
                return "NONE"

            close = df["close"].astype(float).values
            low = df["low"].astype(float).values
            high = df["high"].astype(float).values
            vwap = vwap_series.values

            current_close = close[-1]
            current_vwap = vwap[-1]

            if np.isnan(current_vwap) or current_vwap == 0:
                return "NONE"

            tolerance = current_vwap * (
                self.bounce_tolerance / 100.0
            )

            # Check last 5 candles for touch
            for i in range(-5, -1):
                if abs(i) > len(low):
                    continue

                # BOUNCE UP: low touched VWAP,
                # current close above VWAP
                if abs(low[i] - vwap[i]) <= tolerance:
                    if current_close > current_vwap:
                        print("[VWAP] ⬆️ BOUNCE UP "
                              "from VWAP")
                        return "BOUNCE_UP"

                # BOUNCE DOWN: high touched VWAP,
                # current close below VWAP
                if abs(high[i] - vwap[i]) <= tolerance:
                    if current_close < current_vwap:
                        print("[VWAP] ⬇️ BOUNCE DOWN "
                              "from VWAP")
                        return "BOUNCE_DOWN"

            return "NONE"

        except Exception as e:
            print("[VWAP] ❌ Bounce error: "
                  "{}".format(e))
            return "NONE"
    # ============================================
    # FUNCTION 5: CALCULATE DISTANCE
    # ============================================

    def calculate_distance(self, current_price,
                           current_vwap):
        """
        Calculate percentage distance from VWAP.

        Positive = price above VWAP (bullish bias)
        Negative = price below VWAP (bearish bias)

        Overextension zones:
          > +1.0% → overbought relative to VWAP
          < -1.0% → oversold relative to VWAP
          ±0.3%   → near VWAP (neutral zone)

        Args:
            current_price (float): Latest close
            current_vwap (float):  Latest VWAP value

        Returns:
            dict: {
                "distance_pct": float,
                "is_overextended": bool,
                "zone": "ABOVE"/"BELOW"/"NEAR"
            }
        """
        default = {
            "distance_pct": 0.0,
            "is_overextended": False,
            "zone": "NEAR",
        }

        try:
            if (current_vwap is None or
                    current_vwap <= 0 or
                    current_price is None or
                    current_price <= 0):
                return default

            distance_pct = (
                (current_price - current_vwap)
                / current_vwap
            ) * 100.0

            is_overextended = (
                abs(distance_pct)
                > self.overextend_threshold
            )

            if distance_pct > self.bounce_tolerance:
                zone = "ABOVE"
            elif distance_pct < -self.bounce_tolerance:
                zone = "BELOW"
            else:
                zone = "NEAR"

            return {
                "distance_pct": round(distance_pct, 4),
                "is_overextended": is_overextended,
                "zone": zone,
            }

        except Exception as e:
            print("[VWAP] ❌ Distance error: "
                  "{}".format(e))
            return default

    # ============================================
    # FUNCTION 6: CALCULATE VWAP SLOPE
    # ============================================

    def calculate_slope(self, vwap_series):
        """
        Determine VWAP trend direction.

        Uses net change over slope_period candles
        plus consistency check.

        RISING:  VWAP trending up = bullish pressure
        FALLING: VWAP trending down = bearish pressure
        FLAT:    VWAP sideways = no clear pressure

        Args:
            vwap_series (pd.Series): VWAP values

        Returns:
            str: "RISING", "FALLING", or "FLAT"
        """
        try:
            if vwap_series is None:
                return "FLAT"

            valid = vwap_series.dropna()

            if len(valid) < self.slope_period + 1:
                return "FLAT"

            recent = valid.iloc[-(self.slope_period + 1):]

            first_val = float(recent.iloc[0])
            last_val = float(recent.iloc[-1])

            if first_val == 0:
                return "FLAT"

            # Net change as percentage
            change_pct = (
                (last_val - first_val) / first_val
            ) * 100.0

            # Consistency: count rising vs falling
            diffs = recent.diff().dropna()

            if len(diffs) == 0:
                return "FLAT"

            rising = int((diffs > 0).sum())
            falling = int((diffs < 0).sum())
            total = len(diffs)

            # Need both net change AND consistency
            if (change_pct > 0.05 and
                    rising >= total * 0.6):
                return "RISING"

            if (change_pct < -0.05 and
                    falling >= total * 0.6):
                return "FALLING"

            return "FLAT"

        except Exception as e:
            print("[VWAP] ❌ Slope error: "
                  "{}".format(e))
            return "FLAT"

    # ============================================
    # FUNCTION 7: CHECK VOLUME CONFIRMATION
    # ============================================

    def check_volume_confirmation(self, df):
        """
        Check if current volume supports the move.

        Above-average volume on directional moves
        confirms the move is real, not noise.

        BULLISH_CONFIRMED:
          Price rising + volume above 20-period avg
        BEARISH_CONFIRMED:
          Price falling + volume above 20-period avg
        WEAK:
          Move happening on below-average volume
        NEUTRAL:
          No clear direction

        Args:
            df (DataFrame): Must have close, volume

        Returns:
            str: "BULLISH_CONFIRMED",
                 "BEARISH_CONFIRMED",
                 "WEAK", or "NEUTRAL"
        """
        try:
            if df is None or df.empty:
                return "NEUTRAL"

            if ("close" not in df.columns or
                    "volume" not in df.columns):
                return "NEUTRAL"

            if len(df) < 20:
                return "NEUTRAL"

            close = df["close"].astype(float)
            volume = df["volume"].astype(float)

            # Price direction (last 3 candles)
            price_change = (
                float(close.iloc[-1])
                - float(close.iloc[-3])
            )

            # Volume vs average
            current_vol = float(volume.iloc[-1])
            avg_vol = float(volume.iloc[-20:].mean())

            if avg_vol <= 0:
                return "NEUTRAL"

            vol_ratio = current_vol / avg_vol
            above_avg = vol_ratio >= 1.0

            # Minimum price movement threshold
            price_pct = abs(price_change) / float(
                close.iloc[-3]
            ) * 100.0

            if price_pct < 0.05:
                return "NEUTRAL"

            price_rising = price_change > 0
            price_falling = price_change < 0

            if price_rising and above_avg:
                return "BULLISH_CONFIRMED"

            if price_falling and above_avg:
                return "BEARISH_CONFIRMED"

            if price_rising or price_falling:
                return "WEAK"

            return "NEUTRAL"

        except Exception as e:
            print("[VWAP] ❌ Volume confirm error: "
                  "{}".format(e))
            return "NEUTRAL"
    # ============================================
    # FUNCTION 8: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        MAIN ANALYSIS FUNCTION — Runs all VWAP checks
        and produces a scored trading signal.

        Pipeline:
        1. Calculate VWAP
        2. Check price position vs VWAP
        3. Detect crossover
        4. Detect bounce
        5. Calculate distance (overextension)
        6. Calculate VWAP slope
        7. Check volume confirmation
        8. Score all factors
        9. Direction and confidence

        SCORING:
        Base = 50 (neutral)
        Factor 1: Position (above/below VWAP)  ±10
        Factor 2: Crossover                    ±12
        Factor 3: Bounce                       ±10
        Factor 4: Distance/overextension       ±8
        Factor 5: VWAP slope                   ±8
        Factor 6: Volume confirmation          ±7
        Factor 7: Confluence (4+ agree)        ±5

        Args:
            df (DataFrame): OHLCV data

        Returns:
            dict: Standard brain result format
        """
        neutral_result = {
            "brain": "VWAP",
            "direction": "NEUTRAL",
            "confidence": 0,
            "vwap_value": 0.0,
            "current_price": 0.0,
            "details": {
                "position": "NEAR",
                "crossover": "NONE",
                "bounce": "NONE",
                "distance_pct": 0.0,
                "is_overextended": False,
                "slope": "FLAT",
                "volume_confirmation": "NEUTRAL",
                "bullish_factors": 0,
                "bearish_factors": 0,
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input
            # ============================================
            if df is None or df.empty:
                print("[VWAP] ⚠️ No data provided")
                return neutral_result

            required = ["open", "high", "low",
                        "close", "volume"]
            for col in required:
                if col not in df.columns:
                    print("[VWAP] ⚠️ '{}' missing"
                          .format(col))
                    return neutral_result

            if len(df) < self.min_data_points:
                print("[VWAP] ⚠️ Need {} rows, "
                      "got {}".format(
                          self.min_data_points,
                          len(df),
                      ))
                return neutral_result

            current_price = float(
                df["close"].iloc[-1]
            )

            # ============================================
            # STEP 2: Calculate VWAP
            # ============================================
            vwap_series = self.calculate_vwap(df)

            if vwap_series is None:
                print("[VWAP] ⚠️ VWAP calculation "
                      "failed")
                return neutral_result

            current_vwap = float(vwap_series.iloc[-1])

            if current_vwap <= 0 or np.isnan(
                    current_vwap):
                return neutral_result

            # ============================================
            # STEP 3: Run all sub-analyses
            # ============================================

            # 3a: Price position
            distance = self.calculate_distance(
                current_price, current_vwap
            )
            position = distance["zone"]
            distance_pct = distance["distance_pct"]
            is_overextended = distance[
                "is_overextended"
            ]

            # 3b: Crossover
            closes = df["close"].astype(float).values
            vwap_vals = vwap_series.values
            crossover = self.detect_crossover(
                closes, vwap_vals
            )

            # 3c: Bounce
            bounce = self.detect_bounce(
                df, vwap_series
            )

            # 3d: Slope
            slope = self.calculate_slope(vwap_series)

            # 3e: Volume
            vol_confirm = (
                self.check_volume_confirmation(df)
            )

            # ============================================
            # STEP 4: SCORING
            # ============================================
            score = 50.0
            bullish_factors = 0
            bearish_factors = 0

            # ── Factor 1: Position (±10) ──
            if position == "ABOVE":
                score += self.POINTS["position"]
                bullish_factors += 1
                print("[VWAP] 📈 +{:.0f} pts | Price "
                      "ABOVE VWAP".format(
                          self.POINTS["position"]
                      ))

            elif position == "BELOW":
                score -= self.POINTS["position"]
                bearish_factors += 1
                print("[VWAP] 📉 -{:.0f} pts | Price "
                      "BELOW VWAP".format(
                          self.POINTS["position"]
                      ))

            # ── Factor 2: Crossover (±12) ──
            if crossover == "BULLISH":
                score += self.POINTS["crossover"]
                bullish_factors += 1
                print("[VWAP] 📈 +{:.0f} pts | BULLISH "
                      "crossover".format(
                          self.POINTS["crossover"]
                      ))

            elif crossover == "BEARISH":
                score -= self.POINTS["crossover"]
                bearish_factors += 1
                print("[VWAP] 📉 -{:.0f} pts | BEARISH "
                      "crossover".format(
                          self.POINTS["crossover"]
                      ))

            # ── Factor 3: Bounce (±10) ──
            if bounce == "BOUNCE_UP":
                score += self.POINTS["bounce"]
                bullish_factors += 1
                print("[VWAP] 📈 +{:.0f} pts | Bounce "
                      "UP from VWAP".format(
                          self.POINTS["bounce"]
                      ))

            elif bounce == "BOUNCE_DOWN":
                score -= self.POINTS["bounce"]
                bearish_factors += 1
                print("[VWAP] 📉 -{:.0f} pts | Bounce "
                      "DOWN from VWAP".format(
                          self.POINTS["bounce"]
                      ))

            # ── Factor 4: Distance/Overextension (±8) ──
            # Overextended = price may revert toward VWAP
            # This is a CONTRARIAN signal
            if is_overextended:
                if distance_pct > 0:
                    # Price too far ABOVE VWAP →
                    # may come down (bearish)
                    score -= self.POINTS["distance"]
                    bearish_factors += 1
                    print("[VWAP] 📉 -{:.0f} pts | "
                          "Overextended above VWAP "
                          "({:.2f}%)".format(
                              self.POINTS["distance"],
                              distance_pct,
                          ))
                else:
                    # Price too far BELOW VWAP →
                    # may come up (bullish)
                    score += self.POINTS["distance"]
                    bullish_factors += 1
                    print("[VWAP] 📈 +{:.0f} pts | "
                          "Overextended below VWAP "
                          "({:.2f}%)".format(
                              self.POINTS["distance"],
                              distance_pct,
                          ))

            # ── Factor 5: VWAP Slope (±8) ──
            if slope == "RISING":
                score += self.POINTS["slope"]
                bullish_factors += 1
                print("[VWAP] 📈 +{:.0f} pts | VWAP "
                      "slope RISING".format(
                          self.POINTS["slope"]
                      ))

            elif slope == "FALLING":
                score -= self.POINTS["slope"]
                bearish_factors += 1
                print("[VWAP] 📉 -{:.0f} pts | VWAP "
                      "slope FALLING".format(
                          self.POINTS["slope"]
                      ))

            # ── Factor 6: Volume (±7) ──
            if vol_confirm == "BULLISH_CONFIRMED":
                score += self.POINTS["volume"]
                bullish_factors += 1
                print("[VWAP] 📈 +{:.0f} pts | Volume "
                      "confirms bullish".format(
                          self.POINTS["volume"]
                      ))

            elif vol_confirm == "BEARISH_CONFIRMED":
                score -= self.POINTS["volume"]
                bearish_factors += 1
                print("[VWAP] 📉 -{:.0f} pts | Volume "
                      "confirms bearish".format(
                          self.POINTS["volume"]
                      ))

            elif vol_confirm == "WEAK":
                # Weak volume dampens the score
                # toward neutral slightly
                if score > 55:
                    score -= 3.0
                    print("[VWAP] ⚠️ -3 pts | Weak "
                          "volume dampening")
                elif score < 45:
                    score += 3.0
                    print("[VWAP] ⚠️ +3 pts | Weak "
                          "volume dampening")

            # ── Factor 7: Confluence (±5) ──
            if bullish_factors >= 4:
                score += self.POINTS["confluence"]
                print("[VWAP] 📈 +{:.0f} pts | "
                      "Confluence ({} bullish "
                      "factors)".format(
                          self.POINTS["confluence"],
                          bullish_factors,
                      ))

            elif bearish_factors >= 4:
                score -= self.POINTS["confluence"]
                print("[VWAP] 📉 -{:.0f} pts | "
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
                "brain": "VWAP",
                "direction": direction,
                "confidence": confidence,
                "vwap_value": round(current_vwap, 6),
                "current_price": round(
                    current_price, 6
                ),
                "details": {
                    "position": position,
                    "crossover": crossover,
                    "bounce": bounce,
                    "distance_pct": round(
                        distance_pct, 4
                    ),
                    "is_overextended": is_overextended,
                    "slope": slope,
                    "volume_confirmation": vol_confirm,
                    "bullish_factors": bullish_factors,
                    "bearish_factors": bearish_factors,
                },
            }

            self.results = result

            # ============================================
            # STEP 7: Log summary
            # ============================================
            print("\n[VWAP] ═══════════════════════════"
                  "══════════")
            print("[VWAP]  VWAP Analysis Complete")
            print("[VWAP]  Price       : {:.4f}".format(
                current_price
            ))
            print("[VWAP]  VWAP        : {:.4f}".format(
                current_vwap
            ))
            print("[VWAP]  Position    : {}".format(
                position
            ))
            print("[VWAP]  Distance    : {:.4f}%".format(
                distance_pct
            ))
            print("[VWAP]  Overextended: {}".format(
                is_overextended
            ))
            print("[VWAP]  Crossover   : {}".format(
                crossover
            ))
            print("[VWAP]  Bounce      : {}".format(
                bounce
            ))
            print("[VWAP]  Slope       : {}".format(
                slope
            ))
            print("[VWAP]  Volume      : {}".format(
                vol_confirm
            ))
            print("[VWAP]  Bull/Bear   : {}/{}".format(
                bullish_factors, bearish_factors
            ))
            print("[VWAP]  Score       : {:.1f}/100"
                  .format(score))
            print("[VWAP]  Direction   : {}".format(
                direction
            ))
            print("[VWAP]  Confidence  : {:.1f}%".format(
                confidence
            ))
            print("[VWAP] ═══════════════════════════"
                  "══════════\n")

            return result

        except Exception as e:
            print("[VWAP] ❌ Analysis error: "
                  "{}".format(e))
            return neutral_result


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

vwap_analyzer = VWAPAnalyzer()

print("[VWAP] ✅ VWAP module loaded and ready")                