# ============================================
# CRYPTO SIGNAL BOT - CANDLESTICK PATTERNS
# ============================================
# Brain #7 of 7: Candlestick Pattern Recognition
#
# Detects 16 candlestick patterns:
#   SINGLE (6): Hammer, Inverted Hammer, Shooting Star,
#               Hanging Man, Doji variants, Marubozu
#   DOUBLE (6): Engulfing, Piercing, Dark Cloud,
#               Tweezer Top/Bottom
#   TRIPLE (4): Morning/Evening Star,
#               Three White Soldiers, Three Black Crows
#
# Detection order within single patterns:
#   1. Hammer / Hanging Man (long lower wick shapes)
#   2. Shooting Star / Inverted Hammer (long upper wick shapes)
#   3. Doji variants (extremely small body)
#   4. Marubozu (extremely large body)
#
# This ordering prevents doji from stealing hammer
# detections when the body is very small.
#
# Usage:
#   from algorithms.candle_patterns import candle_analyzer
#   result = candle_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class CandlePatternAnalyzer:
    """
    Candlestick pattern recognition analyzer.

    Detects 16 patterns across single, double, and triple
    candle formations using strict mathematical conditions
    and prior trend context.

    Detection philosophy:
    - STRICT criteria to avoid false positives
    - Shape detection uses RANGE-BASED ratios (not body-based)
      so tiny-body candles don't cause division issues
    - Context (prior trend) required for reversal patterns
    - Returning NEUTRAL is perfectly fine

    Attributes:
        small_body_pct (float):  Body < 30% of range = small
        large_body_pct (float):  Body > 70% of range = large
        doji_pct (float):        Body < 10% of range = doji
        marubozu_pct (float):    Body > 90% of range = marubozu
        min_data_points (int):   Minimum candles needed
    """

    # ============================================
    # PATTERN RELIABILITY SCORES (constant)
    # ============================================

    RELIABILITY = {
        # Strong patterns (75-90)
        "BULLISH_ENGULFING": 83,
        "BEARISH_ENGULFING": 83,
        "MORNING_STAR": 78,
        "EVENING_STAR": 78,
        "THREE_WHITE_SOLDIERS": 82,
        "THREE_BLACK_CROWS": 82,

        # Moderate patterns (55-74)
        "HAMMER": 65,
        "SHOOTING_STAR": 63,
        "PIERCING_LINE": 60,
        "DARK_CLOUD_COVER": 60,
        "TWEEZER_BOTTOM": 58,
        "TWEEZER_TOP": 58,

        # Weak patterns (40-54)
        "INVERTED_HAMMER": 52,
        "HANGING_MAN": 50,
        "DOJI": 48,
        "DRAGONFLY_DOJI": 53,
        "GRAVESTONE_DOJI": 53,
        "BULLISH_MARUBOZU": 55,
        "BEARISH_MARUBOZU": 55,
    }

    # Scoring points by strength tier
    STRENGTH_POINTS = {
        "STRONG": 20.0,
        "MODERATE": 12.0,
        "WEAK": 6.0,
    }

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize the Candlestick Pattern Analyzer.

        Thresholds use RANGE-BASED percentages:
        - All ratios are (measurement / total_range)
        - This avoids division-by-zero when body is tiny
        - A hammer with body=0.2 and range=4.5 has
          body_pct=4.4%, which is fine for shape detection

        Shape detection thresholds:
        - small_body_pct: body < 30% of range = small body
        - large_body_pct: body > 70% of range = large body
        - doji_pct: body < 10% of range = doji
        - marubozu_pct: body > 90% of range = marubozu
        - long_wick_pct: wick > 60% of range = long wick
        - short_wick_pct: wick < 15% of range = short wick
        """
        # ------ Range-based thresholds ------
        self.small_body_pct = 0.30
        self.large_body_pct = 0.70
        self.doji_pct = 0.10
        self.marubozu_pct = 0.90
        self.long_wick_pct = 0.60
        self.short_wick_pct = 0.15

        # ------ Minimum candles needed ------
        self.min_data_points = 15

        # ------ Result storage ------
        self.results = {}

        print("[CANDLE] ✅ Analyzer initialized | "
              "Doji: <{}% | Small: <{}% | Large: >{}%".format(
                  int(self.doji_pct * 100),
                  int(self.small_body_pct * 100),
                  int(self.large_body_pct * 100),
              ))

    # ============================================
    # FUNCTION 2: GET CANDLE PROPERTIES
    # ============================================

    def get_candle_properties(self, row):
        """
        Calculates all properties of a single candle.

        ALL ratios are range-based (divided by total_range)
        to avoid division-by-zero when body is tiny.

        This is the KEY DESIGN DECISION that prevents
        the doji-stealing-hammer bug:
        - upper_wick_pct = upper_wick / total_range
        - lower_wick_pct = lower_wick / total_range
        - body_pct = body_size / total_range

        These three always sum to 1.0 (100% of range).

        Edge cases handled:
        - Flat candle (O=H=L=C): all values = 0
        - NaN values: returns None
        - Negative wicks (bad data): clamped to 0

        Args:
            row: DataFrame row or dict with open/high/low/close

        Returns:
            dict with all candle properties, or None on error
        """
        try:
            # ------ Extract OHLC ------
            if isinstance(row, dict):
                o = float(row.get("open", 0))
                h = float(row.get("high", 0))
                l = float(row.get("low", 0))
                c = float(row.get("close", 0))
            else:
                o = float(row["open"])
                h = float(row["high"])
                l = float(row["low"])
                c = float(row["close"])

            # ------ NaN check ------
            if any(np.isnan(v) for v in [o, h, l, c]):
                return None

            # ------ Core measurements ------
            body_size = abs(c - o)
            total_range = h - l
            upper_wick = max(0.0, h - max(o, c))
            lower_wick = max(0.0, min(o, c) - l)

            # ------ Range-based ratios ------
            # These ALWAYS work, even for doji-like candles
            if total_range > 0:
                body_pct = body_size / total_range
                upper_wick_pct = upper_wick / total_range
                lower_wick_pct = lower_wick / total_range
            else:
                body_pct = 0.0
                upper_wick_pct = 0.0
                lower_wick_pct = 0.0

            # ------ Body-based ratios (for backward compat) ------
            # Only used where explicitly needed
            if body_size > 0:
                upper_wick_ratio = upper_wick / body_size
                lower_wick_ratio = lower_wick / body_size
            else:
                upper_wick_ratio = float("inf") if total_range > 0 else 0.0
                lower_wick_ratio = float("inf") if total_range > 0 else 0.0

            # ------ Classification ------
            is_bullish = c > o
            is_bearish = c < o
            is_doji = body_pct < self.doji_pct and total_range > 0

            return {
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "body_size": body_size,
                "upper_wick": upper_wick,
                "lower_wick": lower_wick,
                "total_range": total_range,
                "is_bullish": is_bullish,
                "is_bearish": is_bearish,
                "is_doji": is_doji,
                # Range-based percentages (primary)
                "body_pct": body_pct,
                "upper_wick_pct": upper_wick_pct,
                "lower_wick_pct": lower_wick_pct,
                # Body-based ratios (legacy/compat)
                "body_ratio": body_pct,
                "upper_wick_ratio": upper_wick_ratio,
                "lower_wick_ratio": lower_wick_ratio,
            }

        except Exception as e:
            print("[CANDLE] ❌ Candle properties error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 3: DETERMINE PRIOR TREND
    # ============================================

    def determine_prior_trend(self, df, index, lookback=10):
        """
        Determines the trend direction before a given candle.

        Uses TWO independent checks that must agree:
        1. Net price change over lookback period
        2. Candle color majority (bullish vs bearish count)

        Both must confirm the same direction.
        If they disagree → SIDEWAYS (no clear trend).

        Thresholds:
        - Price change must be > 0.3% for trend
        - Color majority must be > 55% for trend

        Args:
            df (DataFrame): Must have 'close' and 'open' columns
            index (int):    Position of the candle to check before
            lookback (int): How many candles back to examine

        Returns:
            str: "UPTREND" | "DOWNTREND" | "SIDEWAYS"
        """
        try:
            if df is None or df.empty:
                return "SIDEWAYS"

            start = max(0, index - lookback)
            if start >= index:
                return "SIDEWAYS"

            close_vals = df["close"].astype(float).values
            open_vals = df["open"].astype(float).values

            # ------ Check 1: Net price change ------
            price_start = close_vals[start]
            price_end = close_vals[index - 1] if index > 0 else close_vals[index]

            if price_start == 0:
                return "SIDEWAYS"

            change_pct = ((price_end - price_start) / price_start) * 100.0

            # ------ Check 2: Candle color majority ------
            bullish_count = 0
            bearish_count = 0

            for i in range(start, min(index, len(close_vals))):
                if close_vals[i] > open_vals[i]:
                    bullish_count += 1
                elif close_vals[i] < open_vals[i]:
                    bearish_count += 1

            total = bullish_count + bearish_count
            if total == 0:
                return "SIDEWAYS"

            bullish_pct = bullish_count / total

            # ------ Combine both checks ------
            if change_pct > 0.3 and bullish_pct >= 0.55:
                return "UPTREND"
            elif change_pct < -0.3 and bullish_pct <= 0.45:
                return "DOWNTREND"
            else:
                return "SIDEWAYS"

        except Exception as e:
            print("[CANDLE] ❌ Trend detection error: {}".format(e))
            return "SIDEWAYS"

    # ============================================
    # FUNCTION 4: DETECT SINGLE CANDLE PATTERNS
    # ============================================

    def detect_single_patterns(self, df, index):
        """
        Detects single-candle patterns at the given index.

        DETECTION ORDER IS CRITICAL:
        ┌─────────────────────────────────────────┐
        │ 1. Long-lower-wick shapes (Hammer/HM)   │
        │ 2. Long-upper-wick shapes (SS/IH)        │
        │ 3. Doji variants (only if not shape)     │
        │ 4. Marubozu (large body)                 │
        └─────────────────────────────────────────┘

        Steps 1-2 use range-based percentages:
        - lower_wick_pct >= 60% AND upper_wick_pct < 15%
          = long-lower-wick shape (Hammer or Hanging Man)
        - upper_wick_pct >= 60% AND lower_wick_pct < 15%
          = long-upper-wick shape (Shooting Star or Inv Hammer)

        This catches patterns REGARDLESS of body size.
        A candle with body=0.2 and range=4.5 (body_pct=4.4%)
        is detected as Hammer, NOT Dragonfly Doji.

        After shape detection, doji check only runs if
        no shape pattern was found.

        Patterns detected:
        1. HAMMER - long lower wick shape + downtrend
        2. HANGING_MAN - long lower wick shape + uptrend
        3. SHOOTING_STAR - long upper wick shape + uptrend
        4. INVERTED_HAMMER - long upper wick shape + downtrend
        5. DRAGONFLY_DOJI - doji + long lower wick
        6. GRAVESTONE_DOJI - doji + long upper wick
        7. DOJI - doji + balanced wicks
        8. BULLISH_MARUBOZU - body > 90% range + bullish
        9. BEARISH_MARUBOZU - body > 90% range + bearish

        Args:
            df (DataFrame): Full price data
            index (int):    Candle position to check

        Returns:
            list[dict]: Detected patterns (usually 0 or 1)
        """
        patterns = []

        try:
            if df is None or index < 0 or index >= len(df):
                return patterns

            candle = self.get_candle_properties(df.iloc[index])
            if candle is None:
                return patterns

            # Skip flat / tiny candles
            if candle["total_range"] == 0:
                return patterns

            min_range = candle["close"] * 0.0001
            if candle["total_range"] < min_range:
                return patterns

            trend = self.determine_prior_trend(df, index)

            # Extract range-based percentages
            body_pct = candle["body_pct"]
            upper_pct = candle["upper_wick_pct"]
            lower_pct = candle["lower_wick_pct"]

            # ==========================================
            # SHAPE DETECTION (runs BEFORE doji check)
            # Uses range-based percentages only
            # ==========================================

            shape_found = False

            # ------ LONG LOWER WICK SHAPE ------
            # lower_wick >= 60% of range
            # upper_wick < 15% of range
            # body < 30% of range (small body at top)
            if (lower_pct >= self.long_wick_pct and
                    upper_pct < self.short_wick_pct and
                    body_pct < self.small_body_pct):

                if trend == "DOWNTREND":
                    # HAMMER: long lower wick after downtrend
                    patterns.append({
                        "pattern_name": "HAMMER",
                        "pattern_type": "SINGLE",
                        "signal": "LONG",
                        "strength": "MODERATE",
                        "reliability": self.RELIABILITY["HAMMER"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 🔨 HAMMER detected (bullish reversal)")
                    shape_found = True

                elif trend == "UPTREND":
                    # HANGING MAN: same shape after uptrend
                    patterns.append({
                        "pattern_name": "HANGING_MAN",
                        "pattern_type": "SINGLE",
                        "signal": "SHORT",
                        "strength": "WEAK",
                        "reliability": self.RELIABILITY["HANGING_MAN"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 👤 HANGING MAN detected")
                    shape_found = True

            # ------ LONG UPPER WICK SHAPE ------
            # upper_wick >= 60% of range
            # lower_wick < 15% of range
            # body < 30% of range (small body at bottom)
            if (not shape_found and
                    upper_pct >= self.long_wick_pct and
                    lower_pct < self.short_wick_pct and
                    body_pct < self.small_body_pct):

                if trend == "UPTREND":
                    # SHOOTING STAR: long upper wick after uptrend
                    patterns.append({
                        "pattern_name": "SHOOTING_STAR",
                        "pattern_type": "SINGLE",
                        "signal": "SHORT",
                        "strength": "MODERATE",
                        "reliability": self.RELIABILITY["SHOOTING_STAR"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] ⭐ SHOOTING STAR detected "
                          "(bearish reversal)")
                    shape_found = True

                elif trend == "DOWNTREND":
                    # INVERTED HAMMER: same shape after downtrend
                    patterns.append({
                        "pattern_name": "INVERTED_HAMMER",
                        "pattern_type": "SINGLE",
                        "signal": "LONG",
                        "strength": "WEAK",
                        "reliability": self.RELIABILITY["INVERTED_HAMMER"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 🔨 INVERTED HAMMER detected")
                    shape_found = True

            # ==========================================
            # DOJI DETECTION (only if no shape found)
            # ==========================================
            if not shape_found and candle["is_doji"]:

                # Dragonfly Doji: long lower wick, tiny upper
                if (lower_pct > 0.60 and upper_pct < 0.10):
                    signal = "LONG" if trend == "DOWNTREND" else "NEUTRAL"
                    patterns.append({
                        "pattern_name": "DRAGONFLY_DOJI",
                        "pattern_type": "SINGLE",
                        "signal": signal,
                        "strength": "WEAK",
                        "reliability": self.RELIABILITY["DRAGONFLY_DOJI"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 🐉 DRAGONFLY DOJI detected")

                # Gravestone Doji: long upper wick, tiny lower
                elif (upper_pct > 0.60 and lower_pct < 0.10):
                    signal = "SHORT" if trend == "UPTREND" else "NEUTRAL"
                    patterns.append({
                        "pattern_name": "GRAVESTONE_DOJI",
                        "pattern_type": "SINGLE",
                        "signal": signal,
                        "strength": "WEAK",
                        "reliability": self.RELIABILITY["GRAVESTONE_DOJI"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 🪦 GRAVESTONE DOJI detected")

                # Standard Doji: balanced wicks
                else:
                    patterns.append({
                        "pattern_name": "DOJI",
                        "pattern_type": "SINGLE",
                        "signal": "NEUTRAL",
                        "strength": "WEAK",
                        "reliability": self.RELIABILITY["DOJI"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] ✝ DOJI detected")

            # ==========================================
            # MARUBOZU DETECTION
            # ==========================================
            if not shape_found and body_pct >= self.marubozu_pct:

                if candle["is_bullish"]:
                    patterns.append({
                        "pattern_name": "BULLISH_MARUBOZU",
                        "pattern_type": "SINGLE",
                        "signal": "LONG",
                        "strength": "MODERATE",
                        "reliability": self.RELIABILITY["BULLISH_MARUBOZU"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 📗 BULLISH MARUBOZU detected")

                elif candle["is_bearish"]:
                    patterns.append({
                        "pattern_name": "BEARISH_MARUBOZU",
                        "pattern_type": "SINGLE",
                        "signal": "SHORT",
                        "strength": "MODERATE",
                        "reliability": self.RELIABILITY["BEARISH_MARUBOZU"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 📕 BEARISH MARUBOZU detected")

            return patterns

        except Exception as e:
            print("[CANDLE] ❌ Single pattern error: {}".format(e))
            return patterns

    # ============================================
    # FUNCTION 5: DETECT TWO-CANDLE PATTERNS
    # ============================================

    def detect_two_candle_patterns(self, df, index):
        """
        Detects two-candle patterns using candles at
        index-1 (C1) and index (C2).

        Patterns detected:
        7.  BULLISH_ENGULFING - C2 bullish body covers C1 bearish
        8.  BEARISH_ENGULFING - C2 bearish body covers C1 bullish
        9.  PIERCING_LINE - C2 opens below C1 low, closes > midpoint
        10. DARK_CLOUD_COVER - C2 opens above C1 high, closes < mid
        11. TWEEZER_BOTTOM - same lows, C1 bearish, C2 bullish
        12. TWEEZER_TOP - same highs, C1 bullish, C2 bearish

        Args:
            df (DataFrame): Full price data
            index (int):    Position of second candle (C2)

        Returns:
            list[dict]: Detected patterns
        """
        patterns = []

        try:
            if df is None or index < 1 or index >= len(df):
                return patterns

            c1 = self.get_candle_properties(df.iloc[index - 1])
            c2 = self.get_candle_properties(df.iloc[index])

            if c1 is None or c2 is None:
                return patterns

            if c1["total_range"] == 0 or c2["total_range"] == 0:
                return patterns

            trend = self.determine_prior_trend(df, index - 1)

            # ------ 7. BULLISH ENGULFING ------
            # C1: bearish, C2: bullish
            # C2 body completely covers C1 body
            # Prior: DOWNTREND
            if (c1["is_bearish"] and c2["is_bullish"] and
                    c2["open"] <= c1["close"] and
                    c2["close"] >= c1["open"] and
                    c2["body_size"] > c1["body_size"] and
                    trend == "DOWNTREND"):

                patterns.append({
                    "pattern_name": "BULLISH_ENGULFING",
                    "pattern_type": "DOUBLE",
                    "signal": "LONG",
                    "strength": "STRONG",
                    "reliability": self.RELIABILITY["BULLISH_ENGULFING"],
                    "candles_ago": 0,
                })
                print("[CANDLE] 🟢 BULLISH ENGULFING detected!")

            # ------ 8. BEARISH ENGULFING ------
            # C1: bullish, C2: bearish
            # C2 body completely covers C1 body
            # Prior: UPTREND
            if (c1["is_bullish"] and c2["is_bearish"] and
                    c2["open"] >= c1["close"] and
                    c2["close"] <= c1["open"] and
                    c2["body_size"] > c1["body_size"] and
                    trend == "UPTREND"):

                patterns.append({
                    "pattern_name": "BEARISH_ENGULFING",
                    "pattern_type": "DOUBLE",
                    "signal": "SHORT",
                    "strength": "STRONG",
                    "reliability": self.RELIABILITY["BEARISH_ENGULFING"],
                    "candles_ago": 0,
                })
                print("[CANDLE] 🔴 BEARISH ENGULFING detected!")

            # ------ 9. PIERCING LINE ------
            # C1: bearish, C2: bullish
            # C2 opens below C1 low, closes above C1 midpoint
            # But NOT a full engulfing (C2 close < C1 open)
            # Prior: DOWNTREND
            if (c1["is_bearish"] and c2["is_bullish"] and
                    c2["open"] < c1["low"] and
                    trend == "DOWNTREND"):

                c1_mid = (c1["open"] + c1["close"]) / 2.0
                if c2["close"] > c1_mid and c2["close"] < c1["open"]:
                    patterns.append({
                        "pattern_name": "PIERCING_LINE",
                        "pattern_type": "DOUBLE",
                        "signal": "LONG",
                        "strength": "MODERATE",
                        "reliability": self.RELIABILITY["PIERCING_LINE"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 📌 PIERCING LINE detected")

            # ------ 10. DARK CLOUD COVER ------
            # C1: bullish, C2: bearish
            # C2 opens above C1 high, closes below C1 midpoint
            # But NOT a full engulfing (C2 close > C1 open)
            # Prior: UPTREND
            if (c1["is_bullish"] and c2["is_bearish"] and
                    c2["open"] > c1["high"] and
                    trend == "UPTREND"):

                c1_mid = (c1["open"] + c1["close"]) / 2.0
                if c2["close"] < c1_mid and c2["close"] > c1["open"]:
                    patterns.append({
                        "pattern_name": "DARK_CLOUD_COVER",
                        "pattern_type": "DOUBLE",
                        "signal": "SHORT",
                        "strength": "MODERATE",
                        "reliability": self.RELIABILITY["DARK_CLOUD_COVER"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] ☁ DARK CLOUD COVER detected")

            # ------ 11. TWEEZER BOTTOM ------
            # Same lows (within 0.1%), C1 bearish, C2 bullish
            # Prior: DOWNTREND
            if (c1["is_bearish"] and c2["is_bullish"] and
                    trend == "DOWNTREND"):

                tolerance = max(c1["low"] * 0.001, 0.001)
                if abs(c1["low"] - c2["low"]) <= tolerance:
                    patterns.append({
                        "pattern_name": "TWEEZER_BOTTOM",
                        "pattern_type": "DOUBLE",
                        "signal": "LONG",
                        "strength": "MODERATE",
                        "reliability": self.RELIABILITY["TWEEZER_BOTTOM"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 🔧 TWEEZER BOTTOM detected")

            # ------ 12. TWEEZER TOP ------
            # Same highs (within 0.1%), C1 bullish, C2 bearish
            # Prior: UPTREND
            if (c1["is_bullish"] and c2["is_bearish"] and
                    trend == "UPTREND"):

                tolerance = max(c1["high"] * 0.001, 0.001)
                if abs(c1["high"] - c2["high"]) <= tolerance:
                    patterns.append({
                        "pattern_name": "TWEEZER_TOP",
                        "pattern_type": "DOUBLE",
                        "signal": "SHORT",
                        "strength": "MODERATE",
                        "reliability": self.RELIABILITY["TWEEZER_TOP"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 🔧 TWEEZER TOP detected")

            return patterns

        except Exception as e:
            print("[CANDLE] ❌ Two-candle pattern error: {}".format(e))
            return patterns

    # ============================================
    # FUNCTION 6: DETECT THREE-CANDLE PATTERNS
    # ============================================

    def detect_three_candle_patterns(self, df, index):
        """
        Detects three-candle patterns using candles at
        index-2 (C1), index-1 (C2), and index (C3).

        Patterns detected:
        13. MORNING_STAR - large bearish + small star + large bullish
        14. EVENING_STAR - large bullish + small star + large bearish
        15. THREE_WHITE_SOLDIERS - 3 ascending bullish candles
        16. THREE_BLACK_CROWS - 3 descending bearish candles

        Args:
            df (DataFrame): Full price data
            index (int):    Position of third candle (C3)

        Returns:
            list[dict]: Detected patterns
        """
        patterns = []

        try:
            if df is None or index < 2 or index >= len(df):
                return patterns

            c1 = self.get_candle_properties(df.iloc[index - 2])
            c2 = self.get_candle_properties(df.iloc[index - 1])
            c3 = self.get_candle_properties(df.iloc[index])

            if c1 is None or c2 is None or c3 is None:
                return patterns

            if (c1["total_range"] == 0 or
                    c2["total_range"] == 0 or
                    c3["total_range"] == 0):
                return patterns

            trend = self.determine_prior_trend(df, index - 2)

            # ------ 13. MORNING STAR ------
            # C1: large bearish body (body_pct > 60%)
            # C2: small body (body_pct < 30%) — the "star"
            # C3: large bullish body (body_pct > 60%)
            # C3 closes above C1 midpoint
            # Prior: DOWNTREND
            if (c1["is_bearish"] and
                    c1["body_pct"] >= 0.60 and
                    c2["body_pct"] < self.small_body_pct and
                    c3["is_bullish"] and
                    c3["body_pct"] >= 0.60 and
                    trend == "DOWNTREND"):

                c1_mid = (c1["open"] + c1["close"]) / 2.0
                if c3["close"] > c1_mid:
                    patterns.append({
                        "pattern_name": "MORNING_STAR",
                        "pattern_type": "TRIPLE",
                        "signal": "LONG",
                        "strength": "STRONG",
                        "reliability": self.RELIABILITY["MORNING_STAR"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] ⭐ MORNING STAR detected! "
                          "(strong bullish)")

            # ------ 14. EVENING STAR ------
            # C1: large bullish, C2: small body, C3: large bearish
            # C3 closes below C1 midpoint
            # Prior: UPTREND
            if (c1["is_bullish"] and
                    c1["body_pct"] >= 0.60 and
                    c2["body_pct"] < self.small_body_pct and
                    c3["is_bearish"] and
                    c3["body_pct"] >= 0.60 and
                    trend == "UPTREND"):

                c1_mid = (c1["open"] + c1["close"]) / 2.0
                if c3["close"] < c1_mid:
                    patterns.append({
                        "pattern_name": "EVENING_STAR",
                        "pattern_type": "TRIPLE",
                        "signal": "SHORT",
                        "strength": "STRONG",
                        "reliability": self.RELIABILITY["EVENING_STAR"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 🌙 EVENING STAR detected! "
                          "(strong bearish)")

            # ------ 15. THREE WHITE SOLDIERS ------
            # All 3 bullish, each closes higher, each opens
            # within previous body, small upper wicks
            if (c1["is_bullish"] and
                    c2["is_bullish"] and
                    c3["is_bullish"]):

                closes_ascending = (
                    c2["close"] > c1["close"] and
                    c3["close"] > c2["close"]
                )

                c2_opens_in_c1 = (
                    c2["open"] >= min(c1["open"], c1["close"]) and
                    c2["open"] <= max(c1["open"], c1["close"])
                )
                c3_opens_in_c2 = (
                    c3["open"] >= min(c2["open"], c2["close"]) and
                    c3["open"] <= max(c2["open"], c2["close"])
                )

                small_upper_wicks = all(
                    c["upper_wick"] <= c["body_size"] * 0.3
                    for c in [c1, c2, c3]
                    if c["body_size"] > 0
                )

                if (closes_ascending and c2_opens_in_c1 and
                        c3_opens_in_c2 and small_upper_wicks):

                    patterns.append({
                        "pattern_name": "THREE_WHITE_SOLDIERS",
                        "pattern_type": "TRIPLE",
                        "signal": "LONG",
                        "strength": "STRONG",
                        "reliability": self.RELIABILITY[
                            "THREE_WHITE_SOLDIERS"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 💂 THREE WHITE SOLDIERS detected!")

            # ------ 16. THREE BLACK CROWS ------
            # All 3 bearish, each closes lower, each opens
            # within previous body, small lower wicks
            if (c1["is_bearish"] and
                    c2["is_bearish"] and
                    c3["is_bearish"]):

                closes_descending = (
                    c2["close"] < c1["close"] and
                    c3["close"] < c2["close"]
                )

                c2_opens_in_c1 = (
                    c2["open"] >= min(c1["open"], c1["close"]) and
                    c2["open"] <= max(c1["open"], c1["close"])
                )
                c3_opens_in_c2 = (
                    c3["open"] >= min(c2["open"], c2["close"]) and
                    c3["open"] <= max(c2["open"], c2["close"])
                )

                small_lower_wicks = all(
                    c["lower_wick"] <= c["body_size"] * 0.3
                    for c in [c1, c2, c3]
                    if c["body_size"] > 0
                )

                if (closes_descending and c2_opens_in_c1 and
                        c3_opens_in_c2 and small_lower_wicks):

                    patterns.append({
                        "pattern_name": "THREE_BLACK_CROWS",
                        "pattern_type": "TRIPLE",
                        "signal": "SHORT",
                        "strength": "STRONG",
                        "reliability": self.RELIABILITY[
                            "THREE_BLACK_CROWS"],
                        "candles_ago": 0,
                    })
                    print("[CANDLE] 🐦 THREE BLACK CROWS detected!")

            return patterns

        except Exception as e:
            print("[CANDLE] ❌ Three-candle pattern error: {}".format(e))
            return patterns

    # ============================================
    # FUNCTION 7: DETECT ALL PATTERNS
    # ============================================

    def detect_all_patterns(self, df):
        """
        Runs all pattern detection on the 3 most recent
        candle positions.

        Checks positions:
        - Current candle (candles_ago = 0)
        - Previous candle (candles_ago = 1)
        - Two candles ago (candles_ago = 2)

        Patterns formed 1-2 candles ago are still
        actionable but get reduced weight in scoring.

        Deduplication: if the same pattern appears at
        multiple positions, only the most recent is kept.

        Args:
            df (DataFrame): Full price data

        Returns:
            list[dict]: All unique patterns sorted by
                       reliability (highest first)
        """
        all_patterns = []

        try:
            if df is None or df.empty:
                return all_patterns

            n = len(df)
            if n < self.min_data_points:
                return all_patterns

            # Check 3 most recent positions
            for offset in range(3):
                idx = n - 1 - offset
                if idx < 0:
                    continue

                # Single patterns
                singles = self.detect_single_patterns(df, idx)
                for p in singles:
                    p["candles_ago"] = offset
                all_patterns.extend(singles)

                # Two-candle patterns
                if idx >= 1:
                    doubles = self.detect_two_candle_patterns(df, idx)
                    for p in doubles:
                        p["candles_ago"] = offset
                    all_patterns.extend(doubles)

                # Three-candle patterns
                if idx >= 2:
                    triples = self.detect_three_candle_patterns(df, idx)
                    for p in triples:
                        p["candles_ago"] = offset
                    all_patterns.extend(triples)

            # ------ Deduplicate (keep earliest occurrence) ------
            seen = set()
            unique = []
            for p in all_patterns:
                name = p["pattern_name"]
                if name not in seen:
                    seen.add(name)
                    unique.append(p)

            # ------ Sort by reliability descending ------
            unique.sort(key=lambda x: x["reliability"], reverse=True)

            return unique

        except Exception as e:
            print("[CANDLE] ❌ Pattern detection error: {}".format(e))
            return all_patterns

    # ============================================
    # FUNCTION 8: GET PATTERN RELIABILITY
    # ============================================

    def get_pattern_reliability(self, pattern_name):
        """
        Returns the reliability score for a pattern name.

        Scores based on historical effectiveness:
        - Strong (75-90): Engulfing, Star, Soldiers/Crows
        - Moderate (55-74): Hammer, Shooting Star, Piercing
        - Weak (40-54): Inverted Hammer, Doji, Hanging Man

        Args:
            pattern_name (str): Pattern identifier

        Returns:
            int: Reliability score 0-100, default 40
        """
        return self.RELIABILITY.get(pattern_name, 40)

    # ============================================
    # FUNCTION 9: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        Main analysis function — detects all candlestick
        patterns and produces a scored trading signal.

        Pipeline:
        1.  Validate input (columns, minimum rows)
        2.  Detect all patterns at 3 recent positions
        3.  Separate bullish / bearish / neutral
        4.  Score each pattern by strength tier
        5.  Apply recency decay (older = less impact)
        6.  Multiple pattern bonus (+8 for 2+ same direction)
        7.  Conflicting pattern dampening (×0.5 toward 50)
        8.  Volume confirmation bonus (+5 / -5)
        9.  Clamp score 0-100
        10. Map score to direction and confidence
        11. Determine strongest pattern and context
        12. Build and return result dict

        Scoring:
        Base = 50 (neutral)
        LONG:  +20 strong / +12 moderate / +6 weak / +8 marubozu
        SHORT: -20 strong / -12 moderate / -6 weak / -8 marubozu
        Recency: candles_ago=1 → ×0.8, candles_ago≥2 → ×0.6
        Multi:  2+ bullish → +8, 2+ bearish → -8
        Conflict: both directions → score = 50 + (score-50)×0.5
        Volume: current > 1.5× avg20 → ±5 in score direction

        Score mapping:
        0-30:  SHORT, confidence = (50-score)×2
        30-45: SHORT, confidence = (50-score)×2
        45-55: NEUTRAL, confidence = 0
        55-70: LONG, confidence = (score-50)×2
        70-100: LONG, confidence = (score-50)×2

        Args:
            df (DataFrame): Price data with OHLCV columns

        Returns:
            dict: Standard brain result format with direction,
                  confidence, patterns_found, pattern_count,
                  prior_trend, and details sub-dict
        """
        # ------ Default neutral result ------
        neutral = {
            "brain": "CANDLE_PATTERNS",
            "direction": "NEUTRAL",
            "confidence": 0,
            "patterns_found": [],
            "pattern_count": 0,
            "prior_trend": "SIDEWAYS",
            "details": {
                "total_bullish_patterns": 0,
                "total_bearish_patterns": 0,
                "strongest_pattern": "NONE",
                "strongest_signal": "NEUTRAL",
                "context_appropriate": False,
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input
            # ============================================
            if df is None or df.empty:
                print("[CANDLE] ⚠ No data provided")
                return neutral

            required_cols = ["open", "high", "low", "close"]
            for col in required_cols:
                if col not in df.columns:
                    print("[CANDLE] ⚠ '{}' column missing".format(col))
                    return neutral

            if len(df) < self.min_data_points:
                print("[CANDLE] ⚠ Need {} rows, got {}".format(
                    self.min_data_points, len(df)
                ))
                return neutral

            # ============================================
            # STEP 2: Detect all patterns
            # ============================================
            all_patterns = self.detect_all_patterns(df)
            prior_trend = self.determine_prior_trend(
                df, len(df) - 1
            )

            if not all_patterns:
                result = dict(neutral)
                result["prior_trend"] = prior_trend
                print("[CANDLE] No patterns detected — NEUTRAL")
                return result

            print("[CANDLE] {} pattern(s) detected".format(
                len(all_patterns)
            ))

            # ============================================
            # STEP 3: Separate by direction
            # ============================================
            bullish = [p for p in all_patterns if p["signal"] == "LONG"]
            bearish = [p for p in all_patterns if p["signal"] == "SHORT"]

            # ============================================
            # STEP 4-5: Score with recency decay
            # ============================================
            score = 50.0

            marubozu_names = {"BULLISH_MARUBOZU", "BEARISH_MARUBOZU"}

            # Recency multipliers
            recency_mult = {0: 1.0, 1: 0.8, 2: 0.6}

            for p in bullish:
                name = p["pattern_name"]
                strength = p["strength"]
                ago = p.get("candles_ago", 0)

                if name in marubozu_names:
                    points = 8.0
                else:
                    points = self.STRENGTH_POINTS.get(strength, 6.0)

                points *= recency_mult.get(ago, 0.5)
                score += points

                print("[CANDLE] 📈 +{:.0f} pts | {} ({})".format(
                    points, name, strength
                ))

            for p in bearish:
                name = p["pattern_name"]
                strength = p["strength"]
                ago = p.get("candles_ago", 0)

                if name in marubozu_names:
                    points = 8.0
                else:
                    points = self.STRENGTH_POINTS.get(strength, 6.0)

                points *= recency_mult.get(ago, 0.5)
                score -= points

                print("[CANDLE] 📉 -{:.0f} pts | {} ({})".format(
                    points, name, strength
                ))

            # ============================================
            # STEP 6: Multiple pattern bonus
            # ============================================
            if len(bullish) >= 2:
                score += 8.0
                print("[CANDLE] 📈 +8 pts | Multiple bullish bonus")

            if len(bearish) >= 2:
                score -= 8.0
                print("[CANDLE] 📉 -8 pts | Multiple bearish bonus")

            # ============================================
            # STEP 7: Conflicting pattern dampening
            # ============================================
            has_conflict = len(bullish) > 0 and len(bearish) > 0
            if has_conflict:
                score = 50.0 + (score - 50.0) * 0.5
                print("[CANDLE] ⚠ Conflicting patterns — "
                      "dampened to {:.1f}".format(score))

            # ============================================
            # STEP 8: Volume confirmation
            # ============================================
            if "volume" in df.columns and len(df) >= 20:
                try:
                    vol = df["volume"].astype(float)
                    current_vol = float(vol.iloc[-1])
                    avg_vol = float(vol.iloc[-20:].mean())

                    if avg_vol > 0 and current_vol > avg_vol * 1.5:
                        if score > 50:
                            score += 5.0
                            print("[CANDLE] 📈 +5 pts | Volume "
                                  "confirms bullish")
                        elif score < 50:
                            score -= 5.0
                            print("[CANDLE] 📉 -5 pts | Volume "
                                  "confirms bearish")
                except (ValueError, TypeError):
                    pass  # Skip volume bonus on bad data

            # ============================================
            # STEP 9: Clamp score
            # ============================================
            score = max(0.0, min(100.0, score))

            # ============================================
            # STEP 10: Direction and confidence
            # ============================================
            if score <= 45:
                direction = "SHORT"
                confidence = (50.0 - score) * 2.0
            elif score >= 55:
                direction = "LONG"
                confidence = (score - 50.0) * 2.0
            else:
                direction = "NEUTRAL"
                confidence = 0.0

            confidence = max(0.0, min(100.0, round(confidence, 2)))

            # ============================================
            # STEP 11: Strongest pattern and context
            # ============================================
            strongest = all_patterns[0]  # Sorted by reliability
            strongest_name = strongest["pattern_name"]
            strongest_signal = strongest["signal"]

            # Context check: is the pattern appropriate?
            context_ok = False
            if direction == "NEUTRAL":
                context_ok = True
            elif direction == "LONG" and prior_trend in (
                    "DOWNTREND", "UPTREND"):
                context_ok = True  # Reversal or continuation
            elif direction == "SHORT" and prior_trend in (
                    "UPTREND", "DOWNTREND"):
                context_ok = True

            # ============================================
            # STEP 12: Build result
            # ============================================
            result = {
                "brain": "CANDLE_PATTERNS",
                "direction": direction,
                "confidence": confidence,
                "patterns_found": all_patterns,
                "pattern_count": len(all_patterns),
                "prior_trend": prior_trend,
                "details": {
                    "total_bullish_patterns": len(bullish),
                    "total_bearish_patterns": len(bearish),
                    "strongest_pattern": strongest_name,
                    "strongest_signal": strongest_signal,
                    "context_appropriate": context_ok,
                },
            }

            self.results = result

            # ------ Log summary ------
            print("\n[CANDLE] ═══════════════════════════════════")
            print("[CANDLE]  Candlestick Pattern Analysis")
            print("[CANDLE]  Prior Trend  : {}".format(prior_trend))
            print("[CANDLE]  Patterns     : {} found".format(
                len(all_patterns)))
            print("[CANDLE]  Bullish      : {}".format(len(bullish)))
            print("[CANDLE]  Bearish      : {}".format(len(bearish)))

            for p in all_patterns:
                print("[CANDLE]    {} | {} | {} | Rel: {}".format(
                    p["pattern_name"], p["signal"],
                    p["strength"], p["reliability"]
                ))

            print("[CANDLE]  Strongest    : {}".format(strongest_name))
            print("[CANDLE]  Context OK   : {}".format(context_ok))
            print("[CANDLE]  Conflict     : {}".format(has_conflict))
            print("[CANDLE]  Raw Score    : {:.1f}/100".format(score))
            print("[CANDLE]  Direction    : {}".format(direction))
            print("[CANDLE]  Confidence   : {:.1f}%".format(confidence))
            print("[CANDLE] ═══════════════════════════════════\n")

            return result

        except Exception as e:
            print("[CANDLE] ❌ Analysis error: {}".format(e))
            return neutral


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

candle_analyzer = CandlePatternAnalyzer()

print("[CANDLE] ✅ Candlestick Patterns module loaded and ready")