# ============================================
# CRYPTO SIGNAL BOT - OBV (On Balance Volume)
# ============================================
# Brain 8: On Balance Volume Analysis
#
# OBV = cumulative directed volume indicator.
# Adds volume on up-closes, subtracts on down-closes.
#
# WHY OBV MATTERS:
#   Volume is the FUEL behind price moves.
#   OBV reveals whether real money flows INTO
#   or OUT OF an asset — not just activity.
#
# KEY INSIGHT:
#   OBV rising + price rising = CONFIRMED move
#   OBV falling + price rising = FAKE move (reversal coming)
#   OBV rising + price flat   = ACCUMULATION (bullish)
#   OBV falling + price flat  = DISTRIBUTION (bearish)
#
# MOST VALUABLE SIGNAL — DIVERGENCE:
#   Price lower lows + OBV higher lows = BULLISH
#   Price higher highs + OBV lower highs = BEARISH
#   These are LEADING indicators that predict reversals.
#
# SCORING (7 factors, base=50):
#   Factor 1: OBV Trend (slope)           ±12 pts
#   Factor 2: OBV vs EMA position         ±5  pts
#   Factor 3: EMA crossover timing        ±8  pts
#   Factor 4: Price-OBV confirmation      ±10 pts
#   Factor 5: Divergence (most valuable)  ±15 pts
#   Factor 6: Accumulation/Distribution   ±8  pts
#   Factor 7: Confluence bonus (4+ agree) ±5  pts
#   Range: 0 to 100 (clamped)
#
# Usage:
#   from algorithms.obv import obv_analyzer
#   result = obv_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class OBVAnalyzer:
    """
    On Balance Volume (OBV) analyzer.

    Tracks cumulative volume flow direction to detect:
    - Buying/selling pressure via OBV trend
    - Volume-confirmed moves vs fake moves
    - Price-OBV divergence (leading reversal signals)
    - Institutional accumulation/distribution patterns
    - OBV-EMA crossovers for timing

    All calculations from scratch. No external libraries
    for indicators. Uses numpy for vectorized speed.

    Attributes:
        lookback (int):           Analysis window (20)
        ema_period (int):         OBV-EMA smoothing (10)
        slope_period (int):       Slope measurement window (5)
        divergence_lookback (int): Divergence detection range (20)
        swing_window (int):       Swing point detection radius (2)
        accum_lookback (int):     Accumulation check window (10)
        flat_threshold (float):   Price "flat" = < 0.5% change
        min_data_points (int):    Minimum candles needed (20)
    """

    # ============================================
    # SCORING CONSTANTS
    # ============================================

    POINTS = {
        "trend_strong": 12.0,
        "trend_moderate": 6.0,
        "ema_position": 5.0,
        "ema_crossover": 8.0,
        "confirmation": 10.0,
        "divergence": 15.0,
        "flow": 8.0,
        "confluence": 5.0,
    }

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize OBV Analyzer.

        Parameters tuned for 5-minute crypto candles:
        - lookback=20: ~100 minutes of history for trends
        - ema_period=10: ~50 minutes smoothing for OBV
        - slope_period=5: ~25 minutes for slope direction
        - divergence_lookback=20: ~100 minutes for swing points
        - swing_window=2: requires 2 lower/higher neighbors
        - accum_lookback=10: ~50 minutes for accumulation
        - flat_threshold=0.5%: crypto "flat" price definition
        """
        # ------ Analysis parameters ------
        self.lookback = 20
        self.ema_period = 10
        self.slope_period = 5
        self.divergence_lookback = 20
        self.swing_window = 2
        self.accum_lookback = 10
        self.flat_threshold = 0.5

        # ------ Slope classification thresholds ------
        # Normalized by avg absolute OBV change per candle
        self.steep_threshold = 1.5
        self.moderate_threshold = 0.3

        # ------ Minimum data ------
        self.min_data_points = 20

        # ------ Result storage ------
        self.results = {}

        print("[OBV] ✅ Analyzer initialized | "
              "Lookback: {} | EMA: {} | Slope: {}".format(
                  self.lookback, self.ema_period, self.slope_period
              ))

    # ============================================
    # FUNCTION 2: CALCULATE OBV
    # ============================================

    def calculate_obv(self, closes, volumes):
        """
        Calculate On Balance Volume using vectorized numpy.

        Formula:
        - If close > prev_close: OBV += volume (buyers won)
        - If close < prev_close: OBV -= volume (sellers won)
        - If close == prev_close: OBV unchanged

        Implementation: direction = sign(diff(closes)),
        then OBV = cumsum(direction × volumes).
        Single pass, O(n) time.

        First OBV value is always 0 (starting point).

        Args:
            closes (list/array): Close prices
            volumes (list/array): Volume values

        Returns:
            list: OBV values (same length as input)
        """
        try:
            closes = np.array(closes, dtype=np.float64)
            volumes = np.array(volumes, dtype=np.float64)

            if len(closes) != len(volumes):
                print("[OBV] ❌ Length mismatch: closes={} volumes={}".format(
                    len(closes), len(volumes)
                ))
                return [0.0] * len(closes)

            if len(closes) < 2:
                return [0.0] * len(closes)

            # Replace NaN with 0
            closes = np.nan_to_num(closes, nan=0.0)
            volumes = np.nan_to_num(volumes, nan=0.0)

            # Ensure volumes are non-negative
            volumes = np.abs(volumes)

            # Direction: +1 up, -1 down, 0 flat
            direction = np.zeros(len(closes))
            direction[1:] = np.sign(np.diff(closes))

            # OBV = cumulative sum of directed volume
            obv = np.cumsum(direction * volumes)

            return obv.tolist()

        except Exception as e:
            print("[OBV] ❌ OBV calculation error: {}".format(e))
            return [0.0] * len(closes)

    # ============================================
    # FUNCTION 3: CALCULATE EMA (internal)
    # ============================================

    def _calculate_ema(self, values, period):
        """
        Calculate Exponential Moving Average from scratch.

        Formula:
        - First EMA = SMA of first 'period' values
        - Then: EMA = value × mult + prev_EMA × (1 - mult)
        - Where mult = 2 / (period + 1)

        Returns NaN for the first (period - 1) values
        where EMA is not yet defined.

        Args:
            values (numpy.ndarray): Input values
            period (int): EMA period

        Returns:
            numpy.ndarray: EMA values
        """
        try:
            values = np.array(values, dtype=np.float64)
            n = len(values)
            ema = np.full(n, np.nan)

            if n < period or period < 1:
                return ema

            # First EMA = Simple Moving Average
            ema[period - 1] = np.mean(values[:period])

            # EMA multiplier
            mult = 2.0 / (period + 1)
            inv_mult = 1.0 - mult

            # Forward fill EMA
            for i in range(period, n):
                ema[i] = values[i] * mult + ema[i - 1] * inv_mult

            return ema

        except Exception as e:
            print("[OBV] ❌ EMA calculation error: {}".format(e))
            return np.full(len(values), np.nan)

    # ============================================
    # FUNCTION 4: CALCULATE OBV EMA
    # ============================================

    def calculate_obv_ema(self, obv_values):
        """
        Apply EMA smoothing to OBV values.

        Uses the configured ema_period (default: 10).
        Smooths out single-candle noise in OBV for
        cleaner trend and crossover detection.

        Args:
            obv_values (list/array): Raw OBV values

        Returns:
            list: Smoothed OBV-EMA values
        """
        try:
            obv_arr = np.array(obv_values, dtype=np.float64)
            ema = self._calculate_ema(obv_arr, self.ema_period)
            return ema.tolist()

        except Exception as e:
            print("[OBV] ❌ OBV-EMA error: {}".format(e))
            return [0.0] * len(obv_values)

    # ============================================
    # FUNCTION 5: FIND SWING POINTS (internal)
    # ============================================

    def _find_swing_points(self, values, window=2):
        """
        Find local maxima (swing highs) and local minima
        (swing lows) in a data series.

        A point at index i is a swing HIGH if:
          values[i] > values[i-j] AND values[i] > values[i+j]
          for all j in [1, window]

        A point at index i is a swing LOW if:
          values[i] < values[i-j] AND values[i] < values[i+j]
          for all j in [1, window]

        Cannot detect points within 'window' of either end.

        Args:
            values (numpy.ndarray): Input data series
            window (int): How many neighbors to check each side

        Returns:
            tuple: (swing_highs, swing_lows)
                   Each is list of (index, value) tuples
                   sorted chronologically
        """
        try:
            n = len(values)
            swing_highs = []
            swing_lows = []

            if n < 2 * window + 1:
                return swing_highs, swing_lows

            for i in range(window, n - window):
                is_high = True
                is_low = True

                for j in range(1, window + 1):
                    if values[i] <= values[i - j] or values[i] <= values[i + j]:
                        is_high = False
                    if values[i] >= values[i - j] or values[i] >= values[i + j]:
                        is_low = False

                    # Early exit if neither
                    if not is_high and not is_low:
                        break

                if is_high:
                    swing_highs.append((i, float(values[i])))
                if is_low:
                    swing_lows.append((i, float(values[i])))

            return swing_highs, swing_lows

        except Exception as e:
            print("[OBV] ❌ Swing point error: {}".format(e))
            return [], []

    # ============================================
    # FUNCTION 6: DETECT OBV DIVERGENCE
    # ============================================

    def detect_obv_divergence(self, closes, obv_values):
        """
        Detect price-OBV divergence — the MOST VALUABLE
        signal from OBV analysis.

        BULLISH DIVERGENCE:
        ┌──────────────────────────────────────────┐
        │  Price: makes LOWER lows   (↓)           │
        │  OBV:   makes HIGHER lows  (↑)           │
        │  Meaning: smart money BUYING while       │
        │           price drops — reversal coming   │
        └──────────────────────────────────────────┘

        BEARISH DIVERGENCE:
        ┌──────────────────────────────────────────┐
        │  Price: makes HIGHER highs (↑)           │
        │  OBV:   makes LOWER highs  (↓)           │
        │  Meaning: smart money SELLING while      │
        │           price rises — fake rally        │
        └──────────────────────────────────────────┘

        Method:
        1. Take last N candles (divergence_lookback)
        2. Find swing points in both price and OBV
        3. Compare last 2 swing lows/highs
        4. Require minimum gap between swing points

        Args:
            closes (list/array): Close prices
            obv_values (list/array): OBV values

        Returns:
            str or None: "BULLISH", "BEARISH", or None
        """
        try:
            lookback = self.divergence_lookback

            if len(closes) < lookback or len(obv_values) < lookback:
                return None

            # Use only recent data
            recent_price = np.array(
                closes[-lookback:], dtype=np.float64
            )
            recent_obv = np.array(
                obv_values[-lookback:], dtype=np.float64
            )

            if len(recent_price) < 8:
                return None

            # Find swing points
            window = self.swing_window

            price_highs, price_lows = self._find_swing_points(
                recent_price, window
            )
            obv_highs, obv_lows = self._find_swing_points(
                recent_obv, window
            )

            # Minimum 3-candle gap between swing points
            min_gap = 3

            # ------ BULLISH DIVERGENCE ------
            # Price: lower lows, OBV: higher lows
            if len(price_lows) >= 2 and len(obv_lows) >= 2:
                p_idx1, p_val1 = price_lows[-2]  # older low
                p_idx2, p_val2 = price_lows[-1]  # newer low
                o_idx1, o_val1 = obv_lows[-2]
                o_idx2, o_val2 = obv_lows[-1]

                if (p_idx2 - p_idx1 >= min_gap and
                        o_idx2 - o_idx1 >= min_gap):

                    if p_val2 < p_val1 and o_val2 > o_val1:
                        print("[OBV] 🔍 BULLISH divergence — "
                              "price lower low, OBV higher low")
                        return "BULLISH"

            # ------ BEARISH DIVERGENCE ------
            # Price: higher highs, OBV: lower highs
            if len(price_highs) >= 2 and len(obv_highs) >= 2:
                p_idx1, p_val1 = price_highs[-2]
                p_idx2, p_val2 = price_highs[-1]
                o_idx1, o_val1 = obv_highs[-2]
                o_idx2, o_val2 = obv_highs[-1]

                if (p_idx2 - p_idx1 >= min_gap and
                        o_idx2 - o_idx1 >= min_gap):

                    if p_val2 > p_val1 and o_val2 < o_val1:
                        print("[OBV] 🔍 BEARISH divergence — "
                              "price higher high, OBV lower high")
                        return "BEARISH"

            return None

        except Exception as e:
            print("[OBV] ❌ Divergence detection error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 7: DETECT ACCUMULATION/DISTRIBUTION
    # ============================================

    def detect_accumulation_distribution(self, closes, obv_values):
        """
        Detect institutional accumulation or distribution.

        ACCUMULATION:
        ┌──────────────────────────────────────────┐
        │  Price: FLAT (< 0.5% change over 10)     │
        │  OBV:   RISING consistently (65%+ up)    │
        │  Meaning: big players buying quietly     │
        │           without moving price — bullish  │
        └──────────────────────────────────────────┘

        DISTRIBUTION:
        ┌──────────────────────────────────────────┐
        │  Price: FLAT (< 0.5% change over 10)     │
        │  OBV:   FALLING consistently (65%+ down) │
        │  Meaning: big players selling quietly    │
        │           without moving price — bearish  │
        └──────────────────────────────────────────┘

        Args:
            closes (list/array): Close prices
            obv_values (list/array): OBV values

        Returns:
            str: "ACCUMULATION", "DISTRIBUTION", or "NEUTRAL"
        """
        try:
            period = self.accum_lookback

            if len(closes) < period or len(obv_values) < period:
                return "NEUTRAL"

            recent_closes = np.array(
                closes[-period:], dtype=np.float64
            )
            recent_obv = np.array(
                obv_values[-period:], dtype=np.float64
            )

            # ------ Price flatness check ------
            price_start = recent_closes[0]
            if price_start == 0:
                return "NEUTRAL"

            price_change_pct = abs(
                (recent_closes[-1] - price_start) / price_start
            ) * 100.0

            if price_change_pct > self.flat_threshold:
                return "NEUTRAL"

            # ------ OBV direction consistency ------
            obv_diffs = np.diff(recent_obv)
            total_diffs = len(obv_diffs)

            if total_diffs == 0:
                return "NEUTRAL"

            positive = int(np.sum(obv_diffs > 0))
            negative = int(np.sum(obv_diffs < 0))

            # Need 65%+ consistency
            consistency = 0.65

            if positive >= total_diffs * consistency:
                print("[OBV] 📊 ACCUMULATION — price flat, "
                      "OBV rising ({}/{}  candles up)".format(
                          positive, total_diffs
                      ))
                return "ACCUMULATION"

            if negative >= total_diffs * consistency:
                print("[OBV] 📊 DISTRIBUTION — price flat, "
                      "OBV falling ({}/{} candles down)".format(
                          negative, total_diffs
                      ))
                return "DISTRIBUTION"

            return "NEUTRAL"

        except Exception as e:
            print("[OBV] ❌ Accum/Distrib error: {}".format(e))
            return "NEUTRAL"

    # ============================================
    # FUNCTION 8: GET SIGNAL (Core Computation)
    # ============================================

    def get_signal(self, closes, volumes):
        """
        Generate OBV trading signal from raw price/volume data.

        This is the core computation method. Takes lists of
        closes and volumes, calculates all OBV metrics,
        and returns a scored signal.

        Pipeline:
        1.  Calculate OBV (vectorized cumsum)
        2.  Calculate OBV-EMA (10-period smoothing)
        3.  OBV slope and trend classification
        4.  OBV vs EMA position
        5.  EMA crossover detection (last 3 candles)
        6.  Price-OBV confirmation check
        7.  Divergence detection (swing points)
        8.  Accumulation/distribution detection
        9.  Factor-based scoring (7 factors)
        10. Signal and direction mapping

        Scoring factors:
        ┌───────────────────────────────────────┐
        │ Factor 1: OBV Trend          ±12 pts │
        │ Factor 2: OBV vs EMA         ±5  pts │
        │ Factor 3: EMA Crossover      ±8  pts │
        │ Factor 4: Price Confirmation ±10 pts │
        │ Factor 5: Divergence         ±15 pts │
        │ Factor 6: Flow               ±8  pts │
        │ Factor 7: Confluence         ±5  pts │
        │ Base: 50 | Range: 0-100              │
        └───────────────────────────────────────┘

        Args:
            closes (list): Close prices (minimum 20)
            volumes (list): Volume values (minimum 20)

        Returns:
            dict: Complete signal with score, direction,
                  OBV metrics, divergence, flow, description
        """
        # ------ Default neutral result ------
        default = {
            "brain": "OBV",
            "direction": "NEUTRAL",
            "confidence": 0,
            "score": 50,
            "signal": "NEUTRAL",
            "obv_current": 0.0,
            "obv_ema": 0.0,
            "obv_trend": "FLAT",
            "obv_above_ema": False,
            "price_obv_confirmation": False,
            "divergence": None,
            "flow": "NEUTRAL",
            "description": "Insufficient data for OBV analysis",
            "details": {
                "obv_slope_normalized": 0.0,
                "trend_strength": "NONE",
                "ema_crossover": "NONE",
                "price_slope_pct": 0.0,
                "bullish_factors": 0,
                "bearish_factors": 0,
            },
        }

        try:
            closes = np.array(closes, dtype=np.float64)
            volumes = np.array(volumes, dtype=np.float64)

            if len(closes) < self.min_data_points:
                print("[OBV] ⚠️ Need {} candles, got {}".format(
                    self.min_data_points, len(closes)
                ))
                return default

            # ============================================
            # STEP 1: Calculate OBV
            # ============================================
            obv_list = self.calculate_obv(closes, volumes)
            obv = np.array(obv_list, dtype=np.float64)

            # ============================================
            # STEP 2: Calculate OBV-EMA
            # ============================================
            obv_ema_list = self.calculate_obv_ema(obv_list)
            obv_ema = np.array(obv_ema_list, dtype=np.float64)

            obv_current = float(obv[-1])

            # Handle NaN in EMA (use OBV value as fallback)
            if np.isnan(obv_ema[-1]):
                obv_ema_current = obv_current
            else:
                obv_ema_current = float(obv_ema[-1])

            # ============================================
            # STEP 3: OBV Slope and Trend
            # ============================================
            sp = self.slope_period

            if len(obv) > sp:
                obv_slope = (obv[-1] - obv[-(sp + 1)]) / sp
            else:
                obv_slope = 0.0

            # Normalize slope by avg absolute OBV change
            lookback_slice = obv[-self.lookback:]
            if len(lookback_slice) > 1:
                obv_diffs = np.abs(np.diff(lookback_slice))
                avg_abs_change = float(np.mean(obv_diffs))
            else:
                avg_abs_change = 0.0

            if avg_abs_change > 0:
                normalized_slope = obv_slope / avg_abs_change
            else:
                normalized_slope = 0.0

            # Classify trend
            if abs(normalized_slope) < self.moderate_threshold:
                obv_trend = "FLAT"
                trend_strength = "NONE"
            elif normalized_slope > 0:
                obv_trend = "RISING"
                if normalized_slope > self.steep_threshold:
                    trend_strength = "STRONG"
                else:
                    trend_strength = "MODERATE"
            else:
                obv_trend = "FALLING"
                if normalized_slope < -self.steep_threshold:
                    trend_strength = "STRONG"
                else:
                    trend_strength = "MODERATE"

            # ============================================
            # STEP 4: OBV vs EMA position
            # ============================================
            obv_above_ema = obv_current > obv_ema_current

            # ============================================
            # STEP 5: EMA Crossover (last 3 candles)
            # ============================================
            crossover = "NONE"
            if len(obv) >= 3 and len(obv_ema) >= 3:
                if not np.isnan(obv_ema[-3]):
                    was_above = obv[-3] > obv_ema[-3]
                    now_above = obv[-1] > obv_ema[-1]

                    if now_above and not was_above:
                        crossover = "BULLISH"
                        print("[OBV] 📈 Bullish EMA crossover")
                    elif not now_above and was_above:
                        crossover = "BEARISH"
                        print("[OBV] 📉 Bearish EMA crossover")

            # ============================================
            # STEP 6: Price-OBV Confirmation
            # ============================================
            price_slope_pct = 0.0
            if len(closes) > sp and closes[-(sp + 1)] != 0:
                price_slope_pct = (
                    (closes[-1] - closes[-(sp + 1)])
                    / closes[-(sp + 1)]
                ) * 100.0

            price_up = price_slope_pct > 0.1
            price_down = price_slope_pct < -0.1
            obv_up = normalized_slope > self.moderate_threshold
            obv_down = normalized_slope < -self.moderate_threshold

            confirmation = (
                (price_up and obv_up) or
                (price_down and obv_down)
            )

            # ============================================
            # STEP 7: Divergence Detection
            # ============================================
            divergence = self.detect_obv_divergence(
                closes.tolist(), obv_list
            )

            # ============================================
            # STEP 8: Accumulation/Distribution
            # ============================================
            flow = self.detect_accumulation_distribution(
                closes.tolist(), obv_list
            )

            # ============================================
            # STEP 9: SCORING (7 factors)
            # ============================================
            score = 50.0
            descriptions = []

            # Track factor counts for confluence
            bullish_factors = 0
            bearish_factors = 0

            # ------ Factor 1: OBV Trend (±12) ------
            if obv_trend == "RISING":
                pts = self.POINTS["trend_strong"] if trend_strength == "STRONG" \
                    else self.POINTS["trend_moderate"]
                score += pts
                bullish_factors += 1
                descriptions.append(
                    "OBV rising {}".format(
                        "strongly" if trend_strength == "STRONG"
                        else "moderately"
                    ))
                print("[OBV] 📈 +{:.0f} pts | OBV {} {}".format(
                    pts, obv_trend, trend_strength
                ))

            elif obv_trend == "FALLING":
                pts = self.POINTS["trend_strong"] if trend_strength == "STRONG" \
                    else self.POINTS["trend_moderate"]
                score -= pts
                bearish_factors += 1
                descriptions.append(
                    "OBV falling {}".format(
                        "sharply" if trend_strength == "STRONG"
                        else "moderately"
                    ))
                print("[OBV] 📉 -{:.0f} pts | OBV {} {}".format(
                    pts, obv_trend, trend_strength
                ))

            else:
                descriptions.append("OBV flat (no trend)")

            # ------ Factor 2: OBV vs EMA (±5) ------
            pts = self.POINTS["ema_position"]
            if obv_above_ema:
                score += pts
                bullish_factors += 1
                print("[OBV] 📈 +{:.0f} pts | OBV above EMA".format(pts))
            else:
                score -= pts
                bearish_factors += 1
                print("[OBV] 📉 -{:.0f} pts | OBV below EMA".format(pts))

            # ------ Factor 3: EMA Crossover (±8) ------
            if crossover == "BULLISH":
                pts = self.POINTS["ema_crossover"]
                score += pts
                bullish_factors += 1
                descriptions.append("bullish EMA crossover")
                print("[OBV] 📈 +{:.0f} pts | Bullish crossover".format(
                    pts
                ))
            elif crossover == "BEARISH":
                pts = self.POINTS["ema_crossover"]
                score -= pts
                bearish_factors += 1
                descriptions.append("bearish EMA crossover")
                print("[OBV] 📉 -{:.0f} pts | Bearish crossover".format(
                    pts
                ))

            # ------ Factor 4: Price Confirmation (±10) ------
            if confirmation:
                pts = self.POINTS["confirmation"]
                if price_up:
                    score += pts
                    bullish_factors += 1
                    descriptions.append("price confirms bullish")
                    print("[OBV] 📈 +{:.0f} pts | "
                          "Price-OBV confirmed UP".format(pts))
                else:
                    score -= pts
                    bearish_factors += 1
                    descriptions.append("price confirms bearish")
                    print("[OBV] 📉 -{:.0f} pts | "
                          "Price-OBV confirmed DOWN".format(pts))

            # ------ Factor 5: Divergence (±15) ------
            if divergence == "BULLISH":
                pts = self.POINTS["divergence"]
                score += pts
                bullish_factors += 1
                descriptions.append(
                    "BULLISH divergence (smart money buying)"
                )
                print("[OBV] 📈 +{:.0f} pts | "
                      "BULLISH divergence!".format(pts))

            elif divergence == "BEARISH":
                pts = self.POINTS["divergence"]
                score -= pts
                bearish_factors += 1
                descriptions.append(
                    "BEARISH divergence (smart money selling)"
                )
                print("[OBV] 📉 -{:.0f} pts | "
                      "BEARISH divergence!".format(pts))

            # ------ Factor 6: Flow (±8) ------
            if flow == "ACCUMULATION":
                pts = self.POINTS["flow"]
                score += pts
                bullish_factors += 1
                descriptions.append("institutional accumulation")
                print("[OBV] 📈 +{:.0f} pts | Accumulation".format(pts))

            elif flow == "DISTRIBUTION":
                pts = self.POINTS["flow"]
                score -= pts
                bearish_factors += 1
                descriptions.append("institutional distribution")
                print("[OBV] 📉 -{:.0f} pts | Distribution".format(pts))

            # ------ Factor 7: Confluence Bonus (±5) ------
            if bullish_factors >= 4:
                pts = self.POINTS["confluence"]
                score += pts
                descriptions.append(
                    "{} bullish factors aligned".format(bullish_factors)
                )
                print("[OBV] 📈 +{:.0f} pts | Confluence bonus "
                      "({} bullish)".format(pts, bullish_factors))

            elif bearish_factors >= 4:
                pts = self.POINTS["confluence"]
                score -= pts
                descriptions.append(
                    "{} bearish factors aligned".format(bearish_factors)
                )
                print("[OBV] 📉 -{:.0f} pts | Confluence bonus "
                      "({} bearish)".format(pts, bearish_factors))

            # ------ Clamp score ------
            score = max(0.0, min(100.0, score))

            # ============================================
            # STEP 10: Signal and Direction mapping
            # ============================================
            if score >= 80:
                signal = "STRONG_BUY"
                direction = "LONG"
            elif score >= 65:
                signal = "BUY"
                direction = "LONG"
            elif score >= 55:
                signal = "WEAK_BUY"
                direction = "LONG"
            elif score >= 45:
                signal = "NEUTRAL"
                direction = "NEUTRAL"
            elif score >= 35:
                signal = "WEAK_SELL"
                direction = "SHORT"
            elif score >= 20:
                signal = "SELL"
                direction = "SHORT"
            else:
                signal = "STRONG_SELL"
                direction = "SHORT"

            # Confidence (consistent with other brains)
            if score > 55:
                confidence = min(100.0, (score - 50.0) * 2.0)
            elif score < 45:
                confidence = min(100.0, (50.0 - score) * 2.0)
            else:
                confidence = 0.0

            confidence = round(confidence, 2)

            # Description
            if descriptions:
                description = " | ".join(descriptions)
            else:
                description = "No significant OBV signals"

            # ============================================
            # BUILD RESULT
            # ============================================
            result = {
                "brain": "OBV",
                "direction": direction,
                "confidence": confidence,
                "score": round(score, 2),
                "signal": signal,
                "obv_current": round(obv_current, 2),
                "obv_ema": round(obv_ema_current, 2),
                "obv_trend": obv_trend,
                "obv_above_ema": obv_above_ema,
                "price_obv_confirmation": confirmation,
                "divergence": divergence,
                "flow": flow,
                "description": description,
                "details": {
                    "obv_slope_normalized": round(normalized_slope, 4),
                    "trend_strength": trend_strength,
                    "ema_crossover": crossover,
                    "price_slope_pct": round(price_slope_pct, 4),
                    "bullish_factors": bullish_factors,
                    "bearish_factors": bearish_factors,
                },
            }

            self.results = result

            # ============================================
            # LOG SUMMARY
            # ============================================
            print("\n[OBV] ═══════════════════════════════════")
            print("[OBV]  On Balance Volume Analysis")
            print("[OBV]  OBV Current  : {:,.0f}".format(obv_current))
            print("[OBV]  OBV EMA      : {:,.0f}".format(obv_ema_current))
            print("[OBV]  OBV Trend    : {} ({})".format(
                obv_trend, trend_strength
            ))
            print("[OBV]  Slope (norm) : {:.4f}".format(normalized_slope))
            print("[OBV]  Above EMA    : {}".format(obv_above_ema))
            print("[OBV]  Crossover    : {}".format(crossover))
            print("[OBV]  Confirmed    : {}".format(confirmation))
            print("[OBV]  Divergence   : {}".format(
                divergence if divergence else "None"
            ))
            print("[OBV]  Flow         : {}".format(flow))
            print("[OBV]  Bull/Bear    : {}/{}".format(
                bullish_factors, bearish_factors
            ))
            print("[OBV]  Score        : {:.1f}/100".format(score))
            print("[OBV]  Signal       : {}".format(signal))
            print("[OBV]  Direction    : {}".format(direction))
            print("[OBV]  Confidence   : {:.1f}%".format(confidence))
            print("[OBV] ═══════════════════════════════════\n")

            return result

        except Exception as e:
            print("[OBV] ❌ Signal generation error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 9: ANALYZE (DataFrame Entry Point)
    # ============================================

    def analyze(self, df):
        """
        Main analysis entry point — takes a DataFrame.

        Extracts 'close' and 'volume' columns, validates
        data quality, and delegates to get_signal().

        This is the method called by the signal engine
        for consistency with all other brain modules.

        Args:
            df (DataFrame): Must have 'close' and 'volume'

        Returns:
            dict: Complete OBV analysis result
        """
        default = {
            "brain": "OBV",
            "direction": "NEUTRAL",
            "confidence": 0,
            "score": 50,
            "signal": "NEUTRAL",
            "obv_current": 0.0,
            "obv_ema": 0.0,
            "obv_trend": "FLAT",
            "obv_above_ema": False,
            "price_obv_confirmation": False,
            "divergence": None,
            "flow": "NEUTRAL",
            "description": "No data available",
            "details": {
                "obv_slope_normalized": 0.0,
                "trend_strength": "NONE",
                "ema_crossover": "NONE",
                "price_slope_pct": 0.0,
                "bullish_factors": 0,
                "bearish_factors": 0,
            },
        }

        try:
            if df is None or df.empty:
                print("[OBV] ⚠️ No data provided")
                return default

            # Validate required columns
            required = ["close", "volume"]
            for col in required:
                if col not in df.columns:
                    print("[OBV] ⚠️ '{}' column missing".format(col))
                    return default

            if len(df) < self.min_data_points:
                print("[OBV] ⚠️ Need {} rows, got {}".format(
                    self.min_data_points, len(df)
                ))
                return default

            # Extract as numpy arrays
            closes = df["close"].astype(float).values
            volumes = df["volume"].astype(float).values

            # Check for all-NaN
            if np.all(np.isnan(closes)) or np.all(np.isnan(volumes)):
                print("[OBV] ⚠️ All NaN data")
                return default

            return self.get_signal(closes, volumes)

        except Exception as e:
            print("[OBV] ❌ Analysis error: {}".format(e))
            return default


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

obv_analyzer = OBVAnalyzer()

print("[OBV] ✅ OBV module loaded and ready")