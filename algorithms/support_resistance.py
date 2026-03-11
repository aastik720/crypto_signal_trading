# ============================================
# CRYPTO SIGNAL BOT - SUPPORT & RESISTANCE
# ============================================
# Brain #6 of 7: Support & Resistance Levels
#
# This brain finds KEY PRICE LEVELS where price
# is likely to bounce or reverse. Without it,
# the bot might send LONG signals right below
# major resistance or SHORT signals above major
# support.
#
# This brain answers: "Is price at an important
# level and what will it likely do here?"
#
# Methods used:
#   1. Swing High/Low detection
#   2. Price clustering (group nearby levels)
#   3. Volume-weighted strength scoring
#   4. Bounce / Breakout / Role Reversal detection
#
# Support = price floor (buyers defend)
# Resistance = price ceiling (sellers defend)
#
# All calculations FROM SCRATCH.
#
# Usage:
#   from algorithms.support_resistance import sr_analyzer
#   result = sr_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class SupportResistanceAnalyzer:
    """
    Support & Resistance level analyzer.

    Finds swing highs/lows, clusters them into
    zones, scores their strength, and detects
    bounces, breakouts, and role reversals.

    Attributes:
        swing_lookback (int):       Candles each side for swing
        cluster_threshold (float):  % to group nearby levels
        min_data_points (int):      Minimum candles needed
        results (dict):             Latest analysis results
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self, swing_lookback=5, cluster_threshold=0.5):
        """
        Initialize the Support & Resistance Analyzer.

        Args:
            swing_lookback (int):      Candles on each side to
                                      confirm a swing point.
                                      Default 5 = looks at 5
                                      candles before AND after.
            cluster_threshold (float): Percentage to group
                                      nearby levels. 0.5 means
                                      levels within 0.5% of
                                      each other merge into
                                      one zone.
        """
        self.swing_lookback = swing_lookback
        self.cluster_threshold = cluster_threshold

        # Minimum 30 candles for meaningful S/R analysis
        self.min_data_points = 30

        # Storage for latest results
        self.results = {}

        print("[S/R] ✅ Analyzer initialized | "
              "Lookback: {} | Cluster: {}%".format(
                  self.swing_lookback, self.cluster_threshold
              ))

    # ============================================
    # FUNCTION 2: FIND SWING HIGHS
    # ============================================

    def find_swing_highs(self, df, lookback=None):
        """
        Finds all swing high points in the DataFrame.

        A swing high at index i means the HIGH at that
        candle is greater than the HIGH of all candles
        within 'lookback' distance on both sides.

        For candles near the end of the DataFrame where
        we don't have enough future candles, we use a
        reduced lookback (minimum 2).

        Args:
            df (DataFrame): Must have 'high' and 'volume' columns
            lookback (int): Candles on each side (default from init)

        Returns:
            list[dict]: Each dict has:
                {
                    "price": float,
                    "index": int,
                    "volume_at_level": float
                }
                Empty list on error or no swings found.
        """
        try:
            if df is None or df.empty:
                return []

            if "high" not in df.columns:
                return []

            if lookback is None:
                lookback = self.swing_lookback

            high = df["high"].astype(float).values
            data_length = len(high)

            # Need at least lookback*2 + 1 candles for one swing
            if data_length < 5:
                return []

            # Get volume if available
            has_volume = "volume" in df.columns
            if has_volume:
                volume = df["volume"].astype(float).values
            else:
                volume = np.zeros(data_length)

            swing_highs = []

            # ------ Main scan: full lookback on both sides ------
            for i in range(lookback, data_length - lookback):
                if np.isnan(high[i]):
                    continue

                # Check if high[i] is greater than all neighbors
                is_swing = True

                for j in range(1, lookback + 1):
                    # Check left side
                    if np.isnan(high[i - j]) or high[i] <= high[i - j]:
                        is_swing = False
                        break
                    # Check right side
                    if np.isnan(high[i + j]) or high[i] <= high[i + j]:
                        is_swing = False
                        break

                if is_swing:
                    swing_highs.append({
                        "price": float(high[i]),
                        "index": i,
                        "volume_at_level": float(volume[i]),
                    })

            # ------ Edge scan: reduced lookback for recent candles ------
            # These are the most relevant candles (near current price)
            # Use lookback of 2 for the tail end
            edge_lookback = min(2, lookback)
            edge_start = max(data_length - lookback, lookback)

            for i in range(edge_start, data_length - edge_lookback):
                if np.isnan(high[i]):
                    continue

                # Skip if already found in main scan
                already_found = any(
                    s["index"] == i for s in swing_highs
                )
                if already_found:
                    continue

                is_swing = True
                for j in range(1, edge_lookback + 1):
                    left_idx = i - j
                    right_idx = i + j

                    if left_idx < 0 or right_idx >= data_length:
                        break

                    if (np.isnan(high[left_idx]) or
                            high[i] <= high[left_idx]):
                        is_swing = False
                        break

                    if (np.isnan(high[right_idx]) or
                            high[i] <= high[right_idx]):
                        is_swing = False
                        break

                if is_swing:
                    swing_highs.append({
                        "price": float(high[i]),
                        "index": i,
                        "volume_at_level": float(volume[i]),
                    })

            return swing_highs

        except Exception as e:
            print("[S/R] ❌ Swing high detection error: {}".format(e))
            return []

    # ============================================
    # FUNCTION 3: FIND SWING LOWS
    # ============================================

    def find_swing_lows(self, df, lookback=None):
        """
        Finds all swing low points in the DataFrame.

        A swing low at index i means the LOW at that
        candle is lower than the LOW of all candles
        within 'lookback' distance on both sides.

        Same edge handling as find_swing_highs.

        Args:
            df (DataFrame): Must have 'low' and 'volume' columns
            lookback (int): Candles on each side

        Returns:
            list[dict]: Each dict has price, index, volume_at_level
        """
        try:
            if df is None or df.empty:
                return []

            if "low" not in df.columns:
                return []

            if lookback is None:
                lookback = self.swing_lookback

            low = df["low"].astype(float).values
            data_length = len(low)

            if data_length < 5:
                return []

            has_volume = "volume" in df.columns
            if has_volume:
                volume = df["volume"].astype(float).values
            else:
                volume = np.zeros(data_length)

            swing_lows = []

            # ------ Main scan: full lookback ------
            for i in range(lookback, data_length - lookback):
                if np.isnan(low[i]):
                    continue

                is_swing = True

                for j in range(1, lookback + 1):
                    if np.isnan(low[i - j]) or low[i] >= low[i - j]:
                        is_swing = False
                        break
                    if np.isnan(low[i + j]) or low[i] >= low[i + j]:
                        is_swing = False
                        break

                if is_swing:
                    swing_lows.append({
                        "price": float(low[i]),
                        "index": i,
                        "volume_at_level": float(volume[i]),
                    })

            # ------ Edge scan: reduced lookback ------
            edge_lookback = min(2, lookback)
            edge_start = max(data_length - lookback, lookback)

            for i in range(edge_start, data_length - edge_lookback):
                if np.isnan(low[i]):
                    continue

                already_found = any(
                    s["index"] == i for s in swing_lows
                )
                if already_found:
                    continue

                is_swing = True
                for j in range(1, edge_lookback + 1):
                    left_idx = i - j
                    right_idx = i + j

                    if left_idx < 0 or right_idx >= data_length:
                        break

                    if (np.isnan(low[left_idx]) or
                            low[i] >= low[left_idx]):
                        is_swing = False
                        break

                    if (np.isnan(low[right_idx]) or
                            low[i] >= low[right_idx]):
                        is_swing = False
                        break

                if is_swing:
                    swing_lows.append({
                        "price": float(low[i]),
                        "index": i,
                        "volume_at_level": float(volume[i]),
                    })

            return swing_lows

        except Exception as e:
            print("[S/R] ❌ Swing low detection error: {}".format(e))
            return []

    # ============================================
    # FUNCTION 4: CLUSTER LEVELS
    # ============================================

    def cluster_levels(self, levels, threshold_percent=None):
        """
        Groups nearby price levels into zones.

        Uses sort-and-merge algorithm (O(n log n)):
        1. Sort all levels by price
        2. Walk through sorted list
        3. If next level is within threshold% of current
           cluster, merge it in
        4. Otherwise, close current cluster and start new one

        Each cluster becomes one S/R zone with:
        - Price = average of all levels in cluster
        - Strength = number of touches (levels in cluster)
        - Volume = average volume at those levels

        Args:
            levels (list[dict]): From find_swing_highs/lows.
                                Each dict needs "price", "index",
                                "volume_at_level".
            threshold_percent (float): Merge threshold %.
                                      Default from init.

        Returns:
            list[dict]: Clustered zones sorted by strength:
                {
                    "price": float (zone center),
                    "strength": int (touch count),
                    "touch_count": int,
                    "avg_volume": float,
                    "min_index": int (earliest),
                    "max_index": int (latest),
                    "type": "UNKNOWN" (set later by classify)
                }
        """
        try:
            if not levels:
                return []

            if threshold_percent is None:
                threshold_percent = self.cluster_threshold

            # ------ Step 1: Sort by price ------
            sorted_levels = sorted(levels, key=lambda x: x["price"])

            # ------ Step 2: Merge into clusters ------
            clusters = []
            current_cluster = [sorted_levels[0]]

            for i in range(1, len(sorted_levels)):
                level = sorted_levels[i]
                cluster_avg = sum(
                    l["price"] for l in current_cluster
                ) / len(current_cluster)

                # Check if this level is within threshold of cluster
                if cluster_avg > 0:
                    distance_pct = (
                        abs(level["price"] - cluster_avg) / cluster_avg
                    ) * 100.0
                else:
                    distance_pct = 999.0

                if distance_pct <= threshold_percent:
                    # Merge into current cluster
                    current_cluster.append(level)
                else:
                    # Close current cluster, start new one
                    clusters.append(current_cluster)
                    current_cluster = [level]

            # Don't forget the last cluster
            clusters.append(current_cluster)

            # ------ Step 3: Build zone objects ------
            zones = []

            for cluster in clusters:
                prices = [l["price"] for l in cluster]
                volumes = [l["volume_at_level"] for l in cluster]
                indices = [l["index"] for l in cluster]

                zone = {
                    "price": round(sum(prices) / len(prices), 6),
                    "strength": len(cluster),
                    "touch_count": len(cluster),
                    "avg_volume": round(
                        sum(volumes) / len(volumes), 2
                    ) if volumes else 0.0,
                    "min_index": min(indices),
                    "max_index": max(indices),
                    "type": "UNKNOWN",
                }
                zones.append(zone)

            # ------ Step 4: Sort by strength (descending) ------
            zones.sort(key=lambda x: x["strength"], reverse=True)

            return zones

        except Exception as e:
            print("[S/R] ❌ Clustering error: {}".format(e))
            return []

    # ============================================
    # FUNCTION 5: CLASSIFY LEVELS
    # ============================================

    def classify_levels(self, clustered_levels, current_price):
        """
        Classifies zones as SUPPORT or RESISTANCE based on
        their position relative to current price.

        Levels BELOW current price → SUPPORT
        Levels ABOVE current price → RESISTANCE

        Results are sorted by distance from current price
        (nearest first).

        Args:
            clustered_levels (list[dict]): From cluster_levels()
            current_price (float): Latest close price

        Returns:
            dict: {
                "support_levels": [nearest first],
                "resistance_levels": [nearest first]
            }
        """
        try:
            support = []
            resistance = []

            if not clustered_levels or current_price <= 0:
                return {
                    "support_levels": [],
                    "resistance_levels": [],
                }

            for zone in clustered_levels:
                zone_price = zone["price"]

                # Calculate distance as percentage
                distance_pct = abs(
                    zone_price - current_price
                ) / current_price * 100.0

                zone_copy = dict(zone)
                zone_copy["distance_percent"] = round(distance_pct, 4)

                if zone_price < current_price:
                    zone_copy["type"] = "SUPPORT"
                    support.append(zone_copy)
                elif zone_price > current_price:
                    zone_copy["type"] = "RESISTANCE"
                    resistance.append(zone_copy)
                else:
                    # Exactly at price — treat as both
                    zone_s = dict(zone_copy)
                    zone_s["type"] = "SUPPORT"
                    support.append(zone_s)

                    zone_r = dict(zone_copy)
                    zone_r["type"] = "RESISTANCE"
                    resistance.append(zone_r)

            # Sort by distance (nearest first)
            support.sort(key=lambda x: x["distance_percent"])
            resistance.sort(key=lambda x: x["distance_percent"])

            return {
                "support_levels": support,
                "resistance_levels": resistance,
            }

        except Exception as e:
            print("[S/R] ❌ Classification error: {}".format(e))
            return {
                "support_levels": [],
                "resistance_levels": [],
            }

    # ============================================
    # FUNCTION 6: GET NEAREST SUPPORT
    # ============================================

    def get_nearest_support(self, support_levels, current_price):
        """
        Returns the closest support level below current price.

        Args:
            support_levels (list): Sorted support zones
            current_price (float): Current close price

        Returns:
            dict: {price, distance_percent, strength, touch_count}
            or None if no support found.
        """
        try:
            if not support_levels or current_price <= 0:
                return None

            # support_levels is already sorted nearest first
            nearest = support_levels[0]

            return {
                "price": nearest["price"],
                "distance_percent": round(
                    abs(current_price - nearest["price"])
                    / current_price * 100.0, 4
                ),
                "strength": nearest["strength"],
                "touch_count": nearest["touch_count"],
            }

        except Exception as e:
            print("[S/R] ❌ Nearest support error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 7: GET NEAREST RESISTANCE
    # ============================================

    def get_nearest_resistance(self, resistance_levels, current_price):
        """
        Returns the closest resistance level above current price.

        Args:
            resistance_levels (list): Sorted resistance zones
            current_price (float):    Current close price

        Returns:
            dict: {price, distance_percent, strength, touch_count}
            or None if no resistance found.
        """
        try:
            if not resistance_levels or current_price <= 0:
                return None

            nearest = resistance_levels[0]

            return {
                "price": nearest["price"],
                "distance_percent": round(
                    abs(nearest["price"] - current_price)
                    / current_price * 100.0, 4
                ),
                "strength": nearest["strength"],
                "touch_count": nearest["touch_count"],
            }

        except Exception as e:
            print("[S/R] ❌ Nearest resistance error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 8: IS AT LEVEL
    # ============================================

    def is_at_level(self, current_price, level_price,
                    tolerance_percent=0.3):
        """
        Checks if current price is near a S/R level.

        "Near" means within tolerance_percent of the level.

        Args:
            current_price (float):      Current close price
            level_price (float):        S/R level price
            tolerance_percent (float):  How close = "at level"

        Returns:
            bool: True if within tolerance
        """
        try:
            if current_price <= 0 or level_price <= 0:
                return False

            distance_pct = (
                abs(current_price - level_price) / level_price
            ) * 100.0

            return distance_pct <= tolerance_percent

        except Exception:
            return False

    # ============================================
    # FUNCTION 9: DETECT BOUNCE
    # ============================================

    def detect_bounce(self, df, level_price, level_type,
                      lookback=5):
        """
        Detects price bouncing off a S/R level.

        SUPPORT BOUNCE (bullish):
        - Some candle's low came near support level
        - Price then reversed upward
        - Current close above the low candle's close

        RESISTANCE REJECTION (bearish):
        - Some candle's high came near resistance level
        - Price then reversed downward
        - Current close below the high candle's close

        Args:
            df (DataFrame):      Must have close, high, low
            level_price (float): The S/R level price
            level_type (str):    "SUPPORT" or "RESISTANCE"
            lookback (int):      Candles to check

        Returns:
            dict: {
                "bounce_detected": bool,
                "bounce_type": str,
                "bounce_strength": 0-100,
                "confirmation_candles": int
            }
        """
        default = {
            "bounce_detected": False,
            "bounce_type": "NONE",
            "bounce_strength": 0,
            "confirmation_candles": 0,
        }

        try:
            if df is None or df.empty or level_price <= 0:
                return default

            required = ["close", "high", "low"]
            for col in required:
                if col not in df.columns:
                    return default

            check_count = min(lookback, len(df))
            if check_count < 3:
                return default

            close = df["close"].iloc[-check_count:].astype(float).values
            high = df["high"].iloc[-check_count:].astype(float).values
            low = df["low"].iloc[-check_count:].astype(float).values

            current_close = close[-1]
            tolerance = level_price * 0.003  # 0.3%

            # ------ SUPPORT BOUNCE detection ------
            if level_type == "SUPPORT":
                for i in range(len(low) - 1):
                    # Did this candle touch support?
                    touched = abs(low[i] - level_price) <= tolerance
                    went_below = low[i] <= level_price

                    if touched or went_below:
                        # Did price recover above support?
                        if current_close > level_price:
                            # Count confirmation candles after bounce
                            confirm = 0
                            for j in range(i + 1, len(close)):
                                if close[j] > level_price:
                                    confirm += 1

                            # Strength based on recovery magnitude
                            recovery_pct = (
                                (current_close - level_price)
                                / level_price * 100.0
                            )
                            strength = min(100, int(recovery_pct * 40))
                            strength = max(strength, confirm * 15)

                            print("[S/R] ⬆️ SUPPORT BOUNCE at "
                                  "{:.4f} | Strength: {} | "
                                  "Confirms: {}".format(
                                      level_price, strength, confirm
                                  ))

                            return {
                                "bounce_detected": True,
                                "bounce_type": "SUPPORT_BOUNCE",
                                "bounce_strength": min(100, strength),
                                "confirmation_candles": confirm,
                            }

            # ------ RESISTANCE REJECTION detection ------
            elif level_type == "RESISTANCE":
                for i in range(len(high) - 1):
                    touched = abs(high[i] - level_price) <= tolerance
                    went_above = high[i] >= level_price

                    if touched or went_above:
                        if current_close < level_price:
                            confirm = 0
                            for j in range(i + 1, len(close)):
                                if close[j] < level_price:
                                    confirm += 1

                            rejection_pct = (
                                (level_price - current_close)
                                / level_price * 100.0
                            )
                            strength = min(100, int(rejection_pct * 40))
                            strength = max(strength, confirm * 15)

                            print("[S/R] ⬇️ RESISTANCE REJECTION at "
                                  "{:.4f} | Strength: {} | "
                                  "Confirms: {}".format(
                                      level_price, strength, confirm
                                  ))

                            return {
                                "bounce_detected": True,
                                "bounce_type": "RESISTANCE_REJECTION",
                                "bounce_strength": min(100, strength),
                                "confirmation_candles": confirm,
                            }

            return default

        except Exception as e:
            print("[S/R] ❌ Bounce detection error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 10: DETECT BREAKOUT
    # ============================================

    def detect_breakout(self, df, levels, lookback=3):
        """
        Detects price breaking through a key S/R level.

        BREAKOUT UP criteria:
        - Price closes ABOVE a resistance level
        - At least 2 consecutive candles above it
        - Volume above average (if available)

        BREAKDOWN criteria:
        - Price closes BELOW a support level
        - At least 2 consecutive candles below it

        Checks the strongest (highest touch count) levels
        first since breaking those is more significant.

        Args:
            df (DataFrame):   Must have close, volume
            levels (dict):    Output from classify_levels()
            lookback (int):   Candles to confirm break

        Returns:
            dict: {
                "breakout_detected": bool,
                "breakout_type": "BREAKOUT_UP"/"BREAKDOWN"/"NONE",
                "broken_level": float,
                "level_strength": int,
                "confirmed": bool
            }
        """
        default = {
            "breakout_detected": False,
            "breakout_type": "NONE",
            "broken_level": 0.0,
            "level_strength": 0,
            "confirmed": False,
        }

        try:
            if df is None or df.empty:
                return default

            if not levels:
                return default

            if "close" not in df.columns:
                return default

            close = df["close"].astype(float)
            if len(close) < lookback + 1:
                return default

            # Recent closes for confirmation
            recent_closes = close.iloc[-(lookback + 1):].values

            # Volume check
            vol_confirmed = True
            if "volume" in df.columns:
                vol = df["volume"].astype(float)
                if len(vol) >= 20:
                    current_vol = float(vol.iloc[-1])
                    avg_vol = float(vol.iloc[-20:].mean())
                    vol_confirmed = current_vol > avg_vol * 0.8

            resistance_levels = levels.get("resistance_levels", [])
            support_levels = levels.get("support_levels", [])

            # ------ Check BREAKOUT UP through resistance ------
            # Sort by strength descending (check strongest first)
            for res in sorted(resistance_levels,
                              key=lambda x: x["strength"],
                              reverse=True)[:5]:

                level_price = res["price"]

                # Are all recent closes above this resistance?
                all_above = all(c > level_price for c in recent_closes)
                last_above = recent_closes[-1] > level_price

                if last_above:
                    # Count consecutive candles above
                    consec = 0
                    for c in reversed(recent_closes):
                        if c > level_price:
                            consec += 1
                        else:
                            break

                    confirmed = consec >= 2 and vol_confirmed

                    if consec >= 1:
                        print("[S/R] 🚀 BREAKOUT UP through {:.4f} "
                              "| Strength: {} | Confirmed: {}".format(
                                  level_price, res["strength"],
                                  confirmed
                              ))

                        return {
                            "breakout_detected": True,
                            "breakout_type": "BREAKOUT_UP",
                            "broken_level": level_price,
                            "level_strength": res["strength"],
                            "confirmed": confirmed,
                        }

            # ------ Check BREAKDOWN through support ------
            for sup in sorted(support_levels,
                              key=lambda x: x["strength"],
                              reverse=True)[:5]:

                level_price = sup["price"]
                last_below = recent_closes[-1] < level_price

                if last_below:
                    consec = 0
                    for c in reversed(recent_closes):
                        if c < level_price:
                            consec += 1
                        else:
                            break

                    confirmed = consec >= 2 and vol_confirmed

                    if consec >= 1:
                        print("[S/R] 💥 BREAKDOWN through {:.4f} "
                              "| Strength: {} | Confirmed: {}".format(
                                  level_price, sup["strength"],
                                  confirmed
                              ))

                        return {
                            "breakout_detected": True,
                            "breakout_type": "BREAKDOWN",
                            "broken_level": level_price,
                            "level_strength": sup["strength"],
                            "confirmed": confirmed,
                        }

            return default

        except Exception as e:
            print("[S/R] ❌ Breakout detection error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 11: DETECT ROLE REVERSAL
    # ============================================

    def detect_role_reversal(self, df, levels, lookback=20):
        """
        Detects role reversal: broken S/R acting in opposite role.

        Example 1: Support breaks → price goes below it →
                   price comes back up to it → it now acts
                   as RESISTANCE (old support = new resistance)

        Example 2: Resistance breaks → price goes above →
                   price pulls back to it → it now acts
                   as SUPPORT (old resistance = new support)

        Detection logic:
        1. Find levels that price has crossed (was above, now
           below or vice versa) in the lookback window
        2. Check if price is currently near that level
        3. Check if price is respecting the level in its new role

        Args:
            df (DataFrame): Must have close, high, low
            levels (dict):  Output from classify_levels()
            lookback (int): How far back to check

        Returns:
            dict: {
                "role_reversal_detected": bool,
                "level": float,
                "old_role": str,
                "new_role": str
            }
        """
        default = {
            "role_reversal_detected": False,
            "level": 0.0,
            "old_role": "NONE",
            "new_role": "NONE",
        }

        try:
            if df is None or df.empty or not levels:
                return default

            if "close" not in df.columns:
                return default

            close = df["close"].astype(float)
            actual_lookback = min(lookback, len(close))

            if actual_lookback < 5:
                return default

            recent = close.iloc[-actual_lookback:].values
            current_price = float(recent[-1])
            tolerance = current_price * 0.003  # 0.3%

            all_levels = (
                levels.get("support_levels", []) +
                levels.get("resistance_levels", [])
            )

            for zone in all_levels:
                level_price = zone["price"]

                # Skip levels too far from current price
                dist_pct = abs(
                    current_price - level_price
                ) / current_price * 100.0

                if dist_pct > 1.5:
                    continue

                # Check if price crossed this level in lookback
                was_above = False
                was_below = False

                # Check first half of lookback
                first_half = recent[:actual_lookback // 2]
                second_half = recent[actual_lookback // 2:]

                for val in first_half:
                    if val > level_price:
                        was_above = True
                    if val < level_price:
                        was_below = True

                # Current position
                currently_above = current_price > level_price
                currently_below = current_price < level_price
                currently_near = abs(
                    current_price - level_price
                ) <= tolerance

                # ------ Old resistance → new support ------
                # Was below, broke above, pulled back near level,
                # now holding above it
                if was_below and currently_above and currently_near:
                    # Verify: recent candles staying above level
                    holding = sum(
                        1 for v in second_half if v >= level_price
                    )
                    if holding >= len(second_half) * 0.6:
                        print("[S/R] 🔄 ROLE REVERSAL: {:.4f} "
                              "resistance → support".format(level_price))
                        return {
                            "role_reversal_detected": True,
                            "level": level_price,
                            "old_role": "RESISTANCE",
                            "new_role": "SUPPORT",
                        }

                # ------ Old support → new resistance ------
                if was_above and currently_below and currently_near:
                    holding = sum(
                        1 for v in second_half if v <= level_price
                    )
                    if holding >= len(second_half) * 0.6:
                        print("[S/R] 🔄 ROLE REVERSAL: {:.4f} "
                              "support → resistance".format(level_price))
                        return {
                            "role_reversal_detected": True,
                            "level": level_price,
                            "old_role": "SUPPORT",
                            "new_role": "RESISTANCE",
                        }

            return default

        except Exception as e:
            print("[S/R] ❌ Role reversal error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 12: CALCULATE LEVEL STRENGTH
    # ============================================

    def calculate_level_strength(self, level, df):
        """
        Scores a S/R level's strength from 0-100.

        Factors:
        1. Touch count (more touches = stronger):
           1 touch → 10, 2 → 25, 3 → 45, 4 → 60, 5+ → 80

        2. Recency (recent levels matter more):
           Tested in last 10 candles → +20
           Tested in last 30 candles → +10
           Only tested long ago → +0

        3. Volume (high volume = stronger):
           Volume above average → +10

        Strength capped at 100.

        Args:
            level (dict): Zone dict with touch_count, max_index,
                         avg_volume
            df (DataFrame): For context (total candles, avg volume)

        Returns:
            int: Strength score 0-100
        """
        try:
            strength = 0

            # ------ Factor 1: Touch count ------
            touches = level.get("touch_count", 1)

            touch_scores = {1: 10, 2: 25, 3: 45, 4: 60}
            if touches in touch_scores:
                strength += touch_scores[touches]
            elif touches >= 5:
                strength += 80

            # ------ Factor 2: Recency ------
            max_index = level.get("max_index", 0)
            total_candles = len(df) if df is not None else 0

            if total_candles > 0:
                candles_ago = total_candles - 1 - max_index

                if candles_ago <= 10:
                    strength += 20
                elif candles_ago <= 30:
                    strength += 10
                # Else: +0 (old level)

            # ------ Factor 3: Volume ------
            avg_vol_at_level = level.get("avg_volume", 0)

            if df is not None and "volume" in df.columns and avg_vol_at_level > 0:
                overall_avg = float(df["volume"].mean())
                if overall_avg > 0 and avg_vol_at_level > overall_avg:
                    strength += 10

            return min(100, strength)

        except Exception as e:
            print("[S/R] ❌ Strength calculation error: {}".format(e))
            return 0

    # ============================================
    # FUNCTION 13: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        MAIN ANALYSIS FUNCTION — Finds S/R levels and produces
        a scored trading signal.

        Pipeline:
        1. Find all swing highs and lows
        2. Cluster them into zones
        3. Classify as support or resistance
        4. Score each level's strength
        5. Find nearest support and resistance
        6. Detect bounces, breakouts, role reversals
        7. Calculate composite score (0-100)
        8. Determine direction and confidence

        SCORING SYSTEM:
        Base score = 50 (neutral center)

        LONG factors (add):
        +20  Strong support bounce (strength >= 45)
        +12  Moderate support bounce (strength 25-44)
        +5   Weak support bounce (strength < 25)
        +22  Confirmed breakout above resistance
        +10  Unconfirmed breakout above resistance
        +15  Role reversal (resistance → support holding)
        +8   Price far from resistance (room to run, >1.5%)
        +10  High volume at support
        +10  Multiple support levels nearby (confluence)

        SHORT factors (subtract):
        -20  Strong resistance rejection
        -12  Moderate resistance rejection
        -5   Weak resistance rejection
        -22  Confirmed breakdown below support
        -10  Unconfirmed breakdown below support
        -15  Role reversal (support → resistance holding)
        -8   Price far from support (room to fall, >1.5%)
        -10  High volume at resistance
        -10  Multiple resistance levels nearby (confluence)

        SPECIAL:
        No S/R levels found → return NEUTRAL
        Price far from all levels → dampen toward 50

        Args:
            df (DataFrame): Price data with OHLCV columns

        Returns:
            dict: Standard brain result format
        """
        # ------ Default neutral result ------
        neutral_result = {
            "brain": "SUPPORT_RESISTANCE",
            "direction": "NEUTRAL",
            "confidence": 0,
            "current_price": 0.0,
            "nearest_support": None,
            "nearest_resistance": None,
            "details": {
                "total_support_levels": 0,
                "total_resistance_levels": 0,
                "at_support": False,
                "at_resistance": False,
                "bounce": {
                    "bounce_detected": False,
                    "bounce_type": "NONE",
                    "bounce_strength": 0,
                    "confirmation_candles": 0,
                },
                "breakout": {
                    "breakout_detected": False,
                    "breakout_type": "NONE",
                    "broken_level": 0.0,
                    "level_strength": 0,
                    "confirmed": False,
                },
                "role_reversal": {
                    "role_reversal_detected": False,
                    "level": 0.0,
                    "old_role": "NONE",
                    "new_role": "NONE",
                },
                "support_zones": [],
                "resistance_zones": [],
                "price_position": "MID_RANGE",
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input
            # ============================================
            if df is None or df.empty:
                print("[S/R] ⚠️ No data provided")
                return neutral_result

            required = ["close", "high", "low"]
            for col in required:
                if col not in df.columns:
                    print("[S/R] ⚠️ '{}' column missing".format(col))
                    return neutral_result

            if len(df) < self.min_data_points:
                print("[S/R] ⚠️ Need {} rows, got {}".format(
                    self.min_data_points, len(df)
                ))
                return neutral_result

            current_price = float(df["close"].iloc[-1])

            if current_price <= 0:
                return neutral_result

            # ============================================
            # STEP 2: Find swing points
            # ============================================
            swing_highs = self.find_swing_highs(df)
            swing_lows = self.find_swing_lows(df)

            all_swings = swing_highs + swing_lows

            print("[S/R] Found {} swing highs, {} swing lows".format(
                len(swing_highs), len(swing_lows)
            ))

            if not all_swings:
                print("[S/R] ⚠️ No swing points found")
                return neutral_result

            # ============================================
            # STEP 3: Cluster into zones
            # ============================================
            zones = self.cluster_levels(all_swings)

            if not zones:
                print("[S/R] ⚠️ No zones after clustering")
                return neutral_result

            print("[S/R] Clustered into {} zones".format(len(zones)))

            # ============================================
            # STEP 4: Classify as support/resistance
            # ============================================
            classified = self.classify_levels(zones, current_price)
            support_levels = classified["support_levels"]
            resistance_levels = classified["resistance_levels"]

            # ============================================
            # STEP 5: Score each level's strength
            # ============================================
            for level in support_levels:
                level["calculated_strength"] = (
                    self.calculate_level_strength(level, df)
                )

            for level in resistance_levels:
                level["calculated_strength"] = (
                    self.calculate_level_strength(level, df)
                )

            # ============================================
            # STEP 6: Find nearest levels
            # ============================================
            nearest_sup = self.get_nearest_support(
                support_levels, current_price
            )
            nearest_res = self.get_nearest_resistance(
                resistance_levels, current_price
            )

            # ============================================
            # STEP 7: Check if at a level
            # ============================================
            at_support = False
            at_resistance = False

            if nearest_sup:
                at_support = self.is_at_level(
                    current_price, nearest_sup["price"]
                )

            if nearest_res:
                at_resistance = self.is_at_level(
                    current_price, nearest_res["price"]
                )

            # ============================================
            # STEP 8: Detect bounce
            # ============================================
            bounce_result = {
                "bounce_detected": False,
                "bounce_type": "NONE",
                "bounce_strength": 0,
                "confirmation_candles": 0,
            }

            if at_support and nearest_sup:
                bounce_result = self.detect_bounce(
                    df, nearest_sup["price"], "SUPPORT"
                )

            if not bounce_result["bounce_detected"] and at_resistance and nearest_res:
                bounce_result = self.detect_bounce(
                    df, nearest_res["price"], "RESISTANCE"
                )

            # Also check nearby levels even if not "at" them
            if not bounce_result["bounce_detected"] and nearest_sup:
                if nearest_sup["distance_percent"] < 1.0:
                    bounce_result = self.detect_bounce(
                        df, nearest_sup["price"], "SUPPORT"
                    )

            if not bounce_result["bounce_detected"] and nearest_res:
                if nearest_res["distance_percent"] < 1.0:
                    bounce_result = self.detect_bounce(
                        df, nearest_res["price"], "RESISTANCE"
                    )

            # ============================================
            # STEP 9: Detect breakout
            # ============================================
            breakout_result = self.detect_breakout(
                df, classified, lookback=3
            )

            # ============================================
            # STEP 10: Detect role reversal
            # ============================================
            reversal_result = self.detect_role_reversal(
                df, classified, lookback=20
            )

            # ============================================
            # STEP 11: Determine price position
            # ============================================
            if not support_levels and not resistance_levels:
                price_position = "MID_RANGE"
            elif not support_levels:
                price_position = "BELOW_ALL"
            elif not resistance_levels:
                price_position = "ABOVE_ALL"
            elif at_support:
                price_position = "NEAR_SUPPORT"
            elif at_resistance:
                price_position = "NEAR_RESISTANCE"
            else:
                price_position = "MID_RANGE"

            # ============================================
            # STEP 12: Calculate composite score
            # ============================================
            score = 50.0

            # ------ BOUNCE scoring ------
            if bounce_result["bounce_detected"]:
                b_type = bounce_result["bounce_type"]
                b_strength = bounce_result["bounce_strength"]

                if b_type == "SUPPORT_BOUNCE":
                    # Get level strength from nearest support
                    lvl_str = (nearest_sup.get("strength", 1)
                               if nearest_sup else 1)

                    if lvl_str >= 3:  # Strong: 3+ touches
                        score += 20.0
                        print("[S/R] 📈 +20 pts | STRONG support bounce")
                    elif lvl_str >= 2:
                        score += 12.0
                        print("[S/R] 📈 +12 pts | MODERATE support bounce")
                    else:
                        score += 5.0
                        print("[S/R] 📈 + 5 pts | WEAK support bounce")

                elif b_type == "RESISTANCE_REJECTION":
                    lvl_str = (nearest_res.get("strength", 1)
                               if nearest_res else 1)

                    if lvl_str >= 3:
                        score -= 20.0
                        print("[S/R] 📉 -20 pts | STRONG resistance rejection")
                    elif lvl_str >= 2:
                        score -= 12.0
                        print("[S/R] 📉 -12 pts | MODERATE resistance rejection")
                    else:
                        score -= 5.0
                        print("[S/R] 📉 - 5 pts | WEAK resistance rejection")

            # ------ BREAKOUT scoring ------
            if breakout_result["breakout_detected"]:
                b_type = breakout_result["breakout_type"]
                confirmed = breakout_result["confirmed"]

                if b_type == "BREAKOUT_UP":
                    if confirmed:
                        score += 22.0
                        print("[S/R] 📈 +22 pts | CONFIRMED breakout UP")
                    else:
                        score += 10.0
                        print("[S/R] 📈 +10 pts | Unconfirmed breakout UP")

                elif b_type == "BREAKDOWN":
                    if confirmed:
                        score -= 22.0
                        print("[S/R] 📉 -22 pts | CONFIRMED breakdown")
                    else:
                        score -= 10.0
                        print("[S/R] 📉 -10 pts | Unconfirmed breakdown")

            # ------ ROLE REVERSAL scoring ------
            if reversal_result["role_reversal_detected"]:
                new_role = reversal_result["new_role"]

                if new_role == "SUPPORT":
                    score += 15.0
                    print("[S/R] 📈 +15 pts | Role reversal: "
                          "now SUPPORT")
                elif new_role == "RESISTANCE":
                    score -= 15.0
                    print("[S/R] 📉 -15 pts | Role reversal: "
                          "now RESISTANCE")

            # ------ DISTANCE scoring ------
            if nearest_res and nearest_sup:
                res_dist = nearest_res["distance_percent"]
                sup_dist = nearest_sup["distance_percent"]

                # Far from resistance (room to run up)
                if res_dist > 1.5:
                    score += 8.0
                    print("[S/R] 📈 + 8 pts | Room to run "
                          "({:.2f}% to resistance)".format(res_dist))

                # Far from support (room to fall)
                if sup_dist > 1.5:
                    score -= 8.0
                    print("[S/R] 📉 - 8 pts | Room to fall "
                          "({:.2f}% to support)".format(sup_dist))

            elif nearest_res and not nearest_sup:
                # No support below — bearish
                score -= 5.0

            elif nearest_sup and not nearest_res:
                # No resistance above — bullish
                score += 5.0

            # ------ VOLUME AT LEVEL scoring ------
            if at_support and nearest_sup:
                calc_str = 0
                for s in support_levels[:1]:
                    calc_str = s.get("calculated_strength", 0)

                if calc_str >= 60:
                    score += 10.0
                    print("[S/R] 📈 +10 pts | High-strength "
                          "support (str={})".format(calc_str))

            if at_resistance and nearest_res:
                calc_str = 0
                for r in resistance_levels[:1]:
                    calc_str = r.get("calculated_strength", 0)

                if calc_str >= 60:
                    score -= 10.0
                    print("[S/R] 📉 -10 pts | High-strength "
                          "resistance (str={})".format(calc_str))

            # ------ CONFLUENCE scoring ------
            # Multiple support levels within 1% = confluence
            if len(support_levels) >= 2:
                close_supports = [
                    s for s in support_levels
                    if s["distance_percent"] < 1.0
                ]
                if len(close_supports) >= 2:
                    score += 10.0
                    print("[S/R] 📈 +10 pts | Support confluence "
                          "({} levels within 1%)".format(
                              len(close_supports)
                          ))

            if len(resistance_levels) >= 2:
                close_resistance = [
                    r for r in resistance_levels
                    if r["distance_percent"] < 1.0
                ]
                if len(close_resistance) >= 2:
                    score -= 10.0
                    print("[S/R] 📉 -10 pts | Resistance confluence "
                          "({} levels within 1%)".format(
                              len(close_resistance)
                          ))

            # ------ NO MAN'S LAND adjustment ------
            # If far from all levels, dampen score toward 50
            if nearest_sup and nearest_res:
                if (nearest_sup["distance_percent"] > 2.0 and
                        nearest_res["distance_percent"] > 2.0):
                    score = 50.0 + (score - 50.0) * 0.5
                    print("[S/R] ⚠️ Far from all levels — "
                          "dampened toward neutral")

            # ============================================
            # STEP 13: Clamp score
            # ============================================
            score = max(0.0, min(100.0, score))

            # ============================================
            # STEP 14: Direction and confidence
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
            # STEP 15: Build result
            # ============================================
            # Top 3 zones for details
            top_support = []
            for s in support_levels[:3]:
                top_support.append({
                    "price": s["price"],
                    "touch_count": s["touch_count"],
                    "strength": s.get("calculated_strength", 0),
                    "distance_percent": s["distance_percent"],
                })

            top_resistance = []
            for r in resistance_levels[:3]:
                top_resistance.append({
                    "price": r["price"],
                    "touch_count": r["touch_count"],
                    "strength": r.get("calculated_strength", 0),
                    "distance_percent": r["distance_percent"],
                })

            result = {
                "brain": "SUPPORT_RESISTANCE",
                "direction": direction,
                "confidence": confidence,
                "current_price": round(current_price, 6),
                "nearest_support": nearest_sup,
                "nearest_resistance": nearest_res,
                "details": {
                    "total_support_levels": len(support_levels),
                    "total_resistance_levels": len(resistance_levels),
                    "at_support": at_support,
                    "at_resistance": at_resistance,
                    "bounce": bounce_result,
                    "breakout": breakout_result,
                    "role_reversal": reversal_result,
                    "support_zones": top_support,
                    "resistance_zones": top_resistance,
                    "price_position": price_position,
                },
            }

            self.results = result

            # ============================================
            # STEP 16: Log summary
            # ============================================
            print("\n[S/R] ═══════════════════════════════════")
            print("[S/R]  Support & Resistance Analysis")
            print("[S/R]  Price        : {:.4f}".format(current_price))
            print("[S/R]  Position     : {}".format(price_position))
            print("[S/R]  Support lvls : {}".format(len(support_levels)))
            print("[S/R]  Resist. lvls : {}".format(len(resistance_levels)))

            if nearest_sup:
                print("[S/R]  Nearest Sup  : {:.4f} ({:.2f}% away, "
                      "{} touches)".format(
                          nearest_sup["price"],
                          nearest_sup["distance_percent"],
                          nearest_sup["touch_count"],
                      ))

            if nearest_res:
                print("[S/R]  Nearest Res  : {:.4f} ({:.2f}% away, "
                      "{} touches)".format(
                          nearest_res["price"],
                          nearest_res["distance_percent"],
                          nearest_res["touch_count"],
                      ))

            print("[S/R]  At Support   : {}".format(at_support))
            print("[S/R]  At Resistance: {}".format(at_resistance))

            if bounce_result["bounce_detected"]:
                print("[S/R]  Bounce       : {} (str {})".format(
                    bounce_result["bounce_type"],
                    bounce_result["bounce_strength"],
                ))

            if breakout_result["breakout_detected"]:
                print("[S/R]  Breakout     : {} (confirmed: {})".format(
                    breakout_result["breakout_type"],
                    breakout_result["confirmed"],
                ))

            if reversal_result["role_reversal_detected"]:
                print("[S/R]  Role Reversal: {} → {}".format(
                    reversal_result["old_role"],
                    reversal_result["new_role"],
                ))

            print("[S/R]  Raw Score    : {:.1f}/100".format(score))
            print("[S/R]  Direction    : {}".format(direction))
            print("[S/R]  Confidence   : {:.1f}%".format(confidence))
            print("[S/R] ═══════════════════════════════════\n")

            return result

        except Exception as e:
            print("[S/R] ❌ Analysis error: {}".format(e))
            return neutral_result


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

sr_analyzer = SupportResistanceAnalyzer()

print("[S/R] ✅ Support & Resistance module loaded and ready")