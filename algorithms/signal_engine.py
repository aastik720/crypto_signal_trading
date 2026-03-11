# ============================================
# CRYPTO SIGNAL BOT - SIGNAL ENGINE
# ============================================
# The MASTER BRAIN — combines all 8 individual
# brain outputs into ONE actionable signal.
#
# EVERY 10 MINUTES:
#   1. Fetch data for ALL 10 crypto pairs
#   2. Run ALL 8 brains on EACH pair
#   3. Calculate weighted confidence for each pair
#   4. RANK all 10 pairs by confidence
#   5. Pick the #1 BEST pair
#   6. Send that ONE signal to users
#   7. If no pair above 45% → send "no trade" msg
#   8. Repeat forever 24/7
#
# SIGNAL MEANING:
#   "In the next ~2 minutes, ENTER this trade"
#   Entry  = where to buy/sell NOW
#   Target = where to EXIT with profit
#   Stop   = where to EXIT if wrong
#
# QUALITY TIERS:
#   🟢 75-95% = STRONG (high confidence)
#   🟡 60-74% = MODERATE (trade with caution)
#   🟠 45-59% = WEAK (risky, maybe skip)
#   🔴 < 45%  = NO TRADE (market choppy)
#
# BRAIN WEIGHTS (total = 100):
#   RSI:              15  (momentum king)
#   MACD:             15  (trend direction)
#   EMA Crossover:    13  (trend strength)
#   OBV:              13  (money flow)
#   Bollinger:        12  (volatility)
#   Support/Resist:   12  (key levels)
#   Volume:           10  (activity)
#   Candle Patterns:  10  (price action)
#
# Usage:
#   from algorithms.signal_engine import signal_engine
#   result = await signal_engine.scan_and_pick_best()
# ============================================

import asyncio
import numpy as np
from datetime import datetime, timedelta

from config.settings import Config

# ============================================
# BRAIN IMPORTS (graceful fallback)
# ============================================

BRAIN_REGISTRY = {}

try:
    from algorithms.rsi import rsi_analyzer
    BRAIN_REGISTRY["RSI"] = rsi_analyzer
except ImportError:
    print("[ENGINE] ⚠️ RSI brain not available")

try:
    from algorithms.macd import macd_analyzer
    BRAIN_REGISTRY["MACD"] = macd_analyzer
except ImportError:
    print("[ENGINE] ⚠️ MACD brain not available")

try:
    from algorithms.bollinger import bollinger_analyzer
    BRAIN_REGISTRY["BOLLINGER"] = bollinger_analyzer
except ImportError:
    print("[ENGINE] ⚠️ Bollinger brain not available")

try:
    from algorithms.volume import volume_analyzer
    BRAIN_REGISTRY["VOLUME"] = volume_analyzer
except ImportError:
    print("[ENGINE] ⚠️ Volume brain not available")

try:
    from algorithms.ema_crossover import ema_crossover_analyzer
    BRAIN_REGISTRY["EMA"] = ema_crossover_analyzer
except ImportError:
    print("[ENGINE] ⚠️ EMA brain not available")

try:
    from algorithms.support_resistance import sr_analyzer
    BRAIN_REGISTRY["SUPPORT_RESISTANCE"] = sr_analyzer
except ImportError:
    print("[ENGINE] ⚠️ S/R brain not available")

try:
    from algorithms.candle_patterns import candle_analyzer
    BRAIN_REGISTRY["CANDLE_PATTERNS"] = candle_analyzer
except ImportError:
    print("[ENGINE] ⚠️ Candle brain not available")

try:
    from algorithms.obv import obv_analyzer
    BRAIN_REGISTRY["OBV"] = obv_analyzer
except ImportError:
    print("[ENGINE] ⚠️ OBV brain not available")

# ============================================
# DATA FETCHER
# ============================================

try:
    from data.fetcher import fetcher as data_fetcher
except ImportError:
    data_fetcher = None
    print("[ENGINE] ⚠️ Data fetcher not available")

# ============================================
# LOGGER & TRACKER
# ============================================

try:
    from utils.logger import bot_logger, performance_tracker
except ImportError:
    bot_logger = None
    performance_tracker = None

# ============================================
# CONSTANTS
# ============================================

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Quality tier thresholds
TIER_STRONG = 75
TIER_MODERATE = 60
TIER_WEAK = 45
TIER_NO_TRADE = 0

# Quality tier labels
QUALITY_TIERS = {
    "STRONG": {"min": 75, "emoji": "🟢", "label": "STRONG SIGNAL"},
    "MODERATE": {"min": 60, "emoji": "🟡", "label": "MODERATE SIGNAL"},
    "WEAK": {"min": 45, "emoji": "🟠", "label": "WEAK SIGNAL"},
    "NO_TRADE": {"min": 0, "emoji": "🔴", "label": "NO TRADE"},
}


class SignalEngine:
    """
    Master signal generation engine.

    Combines 8 independent analysis brains into
    a single weighted consensus. Scans all pairs,
    ranks them, and picks ONLY the #1 best signal.

    Every 10 minutes:
    - Scan all 10 pairs
    - Run 8 brains on each
    - Rank by confidence
    - Pick #1 best
    - Send signal or "no trade" message

    Attributes:
        _brains (dict):          Available brain instances
        brain_weights (dict):    Normalized weights (sum=100)
        min_brains (int):        Min brains needed to vote
        signal_cooldowns (dict): Cooldown tracker per pair
        _last_signals (dict):    Cache of last signal per pair
        _signal_count (int):     Lifetime signal count
        _scan_count (int):       Lifetime scan count
        _no_trade_count (int):   Times "no trade" was sent
        trading_pairs (list):    Pairs to scan
    """

    # ============================================
    # BRAIN WEIGHTS (sum = 100)
    # ============================================

    DEFAULT_WEIGHTS = {
        "RSI": 15,
        "MACD": 15,
        "EMA": 13,
        "OBV": 13,
        "BOLLINGER": 12,
        "SUPPORT_RESISTANCE": 12,
        "VOLUME": 10,
        "CANDLE_PATTERNS": 10,
    }

    # Direction to numeric score mapping
    DIRECTION_SCORE = {
        "LONG": 1.0,
        "SHORT": -1.0,
        "NEUTRAL": 0.0,
    }

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize the Signal Engine.

        Maps available brains, normalizes weights,
        loads trading pairs from Config.
        """
        # ------ Brain registry (only available ones) ------
        self._brains = dict(BRAIN_REGISTRY)

        # ------ Normalize weights for available brains ------
        self.brain_weights = self._normalize_weights()

        # ------ Minimum brains to produce signal ------
        self.min_brains = 3

        # ------ Cooldown tracking ------
        # {pair: last_signal_datetime}
        self.signal_cooldowns = {}
        self.cooldown_minutes = 10

        # ------ Signal cache ------
        self._last_signals = {}
        self._signal_count = 0
        self._scan_count = 0
        self._no_trade_count = 0

        # ------ Trading pairs ------
        try:
            self.trading_pairs = Config.TRADING_PAIRS
        except AttributeError:
            self.trading_pairs = [
                "BTC/USDT", "ETH/USDT", "BNB/USDT",
                "SOL/USDT", "XRP/USDT", "ADA/USDT",
                "AVAX/USDT", "DOGE/USDT", "DOT/USDT",
                "MATIC/USDT",
            ]

        # ------ Config ------
        try:
            self.scan_interval = int(Config.SIGNAL_INTERVAL_MINUTES)
        except (AttributeError, ValueError, TypeError):
            self.scan_interval = 10

        print("[ENGINE] ✅ Signal Engine initialized")
        print("[ENGINE]    Active brains: {}/8".format(
            len(self._brains)
        ))
        print("[ENGINE]    Brains: {}".format(
            ", ".join(self._brains.keys())
        ))
        print("[ENGINE]    Weights: {}".format(self.brain_weights))
        print("[ENGINE]    Pairs: {} pairs".format(
            len(self.trading_pairs)
        ))
        print("[ENGINE]    Scan interval: {} min".format(
            self.scan_interval
        ))

    # ============================================
    # FUNCTION 2: NORMALIZE WEIGHTS
    # ============================================

    def _normalize_weights(self):
        """
        Normalize brain weights so available brains
        sum to exactly 100.

        Missing brains have their weight redistributed
        proportionally to remaining brains.

        Returns:
            dict: {brain_name: normalized_weight}
        """
        try:
            raw = {}
            total = 0

            for name in self._brains:
                w = self.DEFAULT_WEIGHTS.get(name, 10)
                raw[name] = w
                total += w

            if total == 0:
                return raw

            normalized = {}
            for name, w in raw.items():
                normalized[name] = round((w / total) * 100, 2)

            return normalized

        except Exception:
            count = max(1, len(self._brains))
            return {n: round(100 / count, 2) for n in self._brains}

    # ============================================
    # FUNCTION 3: RUN SINGLE BRAIN (safe)
    # ============================================

    def _run_brain(self, brain_name, brain_instance, df):
        """
        Run one brain's analysis with full error isolation.

        One brain crashing NEVER stops the engine.

        The brains return:
            "direction":  LONG / SHORT / NEUTRAL
            "confidence": 0-100

        But they do NOT return "score" in the dict.
        The score is calculated INTERNALLY by each brain
        and used to derive direction + confidence, but
        it is not included in the return dictionary.

        So we REVERSE-ENGINEER the score from direction
        and confidence using the same formula the brains
        use internally:

            LONG:  score = 50 + (confidence / 2)
            SHORT: score = 50 - (confidence / 2)
            NEUTRAL: score = 50

        This gives us back the original 0-100 score
        that the engine needs for weighted voting.

        Examples:
            RSI  → LONG  80% conf → score = 90
            MACD → SHORT 60% conf → score = 20
            EMA  → LONG  40% conf → score = 70
            OBV  → NEUTRAL 0% conf → score = 50

        Args:
            brain_name (str):   Brain identifier
            brain_instance:     Brain analyzer object
            df (DataFrame):     OHLCV price data

        Returns:
            dict or None: Brain result with direction,
                         confidence, and score.
                         None on error.
        """
        try:
            result = brain_instance.analyze(df)

            if result is None:
                return None

            # ------ Extract direction and confidence ------
            direction = result.get("direction", "NEUTRAL")
            confidence = result.get("confidence", 0)

            # ------ Normalize direction ------
            if direction not in ("LONG", "SHORT", "NEUTRAL"):
                direction = "NEUTRAL"

            # ------ Clamp confidence to 0-100 ------
            confidence = max(0.0, min(100.0, float(confidence)))

            # ------ Derive score from direction + confidence ------
            # Brains do NOT return "score" in their dict.
            # They calculate it internally (0-100 scale):
            #   50 = neutral center
            #   >50 = bullish (LONG)
            #   <50 = bearish (SHORT)
            #
            # They then convert score to confidence:
            #   confidence = abs(score - 50) * 2
            #
            # We reverse that formula to get score back:
            #   score = 50 + (confidence / 2)  for LONG
            #   score = 50 - (confidence / 2)  for SHORT
            #   score = 50                     for NEUTRAL

            score = result.get("score", None)

            if score is None:
                if direction == "LONG":
                    score = 50.0 + (confidence / 2.0)
                elif direction == "SHORT":
                    score = 50.0 - (confidence / 2.0)
                else:
                    score = 50.0

            # ------ Clamp score to 0-100 ------
            score = max(0.0, min(100.0, float(score)))

            # ------ Write back to result ------
            result["direction"] = direction
            result["confidence"] = confidence
            result["score"] = score

            return result

        except Exception as e:
            print("[ENGINE] ❌ {} brain error: {}".format(
                brain_name, e
            ))
            if bot_logger:
                bot_logger.log_error(
                    "ENGINE.{}".format(brain_name), e
                )
            return None

    # ============================================
    # FUNCTION 4: RUN ALL 8 BRAINS
    # ============================================

    def run_all_brains(self, df):
        """
        Run all available brains on the price data.

        Each brain runs independently. Failed brains
        return None and are excluded from voting.

        Args:
            df (DataFrame): OHLCV price data

        Returns:
            dict: {brain_name: result_dict or None}
        """
        results = {}

        try:
            if df is None or df.empty:
                print("[ENGINE] ⚠️ No data for analysis")
                return results

            for name, instance in self._brains.items():
                result = self._run_brain(name, instance, df)
                results[name] = result

                if result:
                    d = result.get("direction", "?")
                    c = result.get("confidence", 0)
                    s = result.get("score", 50)
                    print("[ENGINE]     {} → {} | "
                          "conf: {:.0f}% | score: {:.0f}".format(
                              name, d, c, s
                          ))

                    if bot_logger:
                        bot_logger.log_brain_result(name, result)
                else:
                    print("[ENGINE]     {} → FAILED".format(name))

            return results

        except Exception as e:
            print("[ENGINE] ❌ Run all brains error: {}".format(e))
            return results

    # ============================================
    # FUNCTION 5: COMBINE SIGNALS (core algorithm)
    # ============================================

    def combine_signals(self, brain_results, pair, current_price):
        """
        THE CORE ALGORITHM — combines all brain votes
        into one final signal.

        Pipeline:
        ┌──────────────────────────────────────┐
        │ Step 1: Calculate weighted score     │
        │ Step 2: Determine direction          │
        │ Step 3: Calculate base confidence    │
        │ Step 4: Agreement bonus/penalty      │
        │ Step 5: Special pattern bonuses      │
        │ Step 6: Cap confidence at 95%        │
        │ Step 7: Determine quality tier       │
        │ Step 8: Calculate trade levels       │
        │ Step 9: Build final signal           │
        └──────────────────────────────────────┘

        Args:
            brain_results (dict):  Results from run_all_brains()
            pair (str):            Trading pair name
            current_price (float): Latest close price

        Returns:
            dict: Complete signal with all fields
        """
        try:
            # ============================================
            # STEP 1: Calculate Weighted Score
            # ============================================
            weighted_sum = 0.0
            total_weight_used = 0.0
            active_brains = 0

            brain_directions = []
            brain_details = {}

            for brain_name, result in brain_results.items():
                if result is None:
                    continue

                score = result.get("score", 50)
                weight = self.brain_weights.get(brain_name, 0)
                direction = result.get("direction", "NEUTRAL")
                confidence = result.get("confidence", 0)

                weighted_sum += score * (weight / 100.0)
                total_weight_used += weight / 100.0
                active_brains += 1

                brain_directions.append(direction)

                brain_details[brain_name] = {
                    "direction": direction,
                    "confidence": confidence,
                    "score": score,
                }

            # Not enough brains
            if active_brains < self.min_brains:
                print("[ENGINE]   ⚠️ Only {} brains "
                      "(need {})".format(
                          active_brains, self.min_brains
                      ))
                return self._build_no_trade_signal(
                    pair, current_price, brain_details,
                    active_brains, 0,
                    "Not enough brains responded"
                )

            # Normalize weighted score
            if total_weight_used > 0:
                weighted_score = weighted_sum / total_weight_used
            else:
                weighted_score = 50.0

            # ============================================
            # STEP 2: Determine Direction
            # ============================================
            if weighted_score > 55:
                direction = "LONG"
            elif weighted_score < 45:
                direction = "SHORT"
            else:
                direction = "NEUTRAL"

            # ============================================
            # STEP 3: Calculate Base Confidence
            # ============================================
            if direction == "LONG":
                base_confidence = min(
                    ((weighted_score - 50) / 50) * 100, 100
                )
            elif direction == "SHORT":
                base_confidence = min(
                    ((50 - weighted_score) / 50) * 100, 100
                )
            else:
                base_confidence = 0

            # ============================================
            # STEP 4: Agreement Bonus / Penalty
            # ============================================
            long_count = brain_directions.count("LONG")
            short_count = brain_directions.count("SHORT")
            neutral_count = brain_directions.count("NEUTRAL")

            if direction == "LONG":
                agreeing = long_count
            elif direction == "SHORT":
                agreeing = short_count
            else:
                agreeing = neutral_count

            agree_ratio = agreeing / max(1, active_brains)

            if agree_ratio >= 0.75:
                # 6+ of 8 agree → +15%
                agreement_bonus = 15
                agreement_level = "STRONG"
            elif agree_ratio >= 0.60:
                # 5 of 8 agree → +8%
                agreement_bonus = 8
                agreement_level = "MODERATE"
            elif agree_ratio >= 0.50:
                # 4 of 8 agree → +0%
                agreement_bonus = 0
                agreement_level = "WEAK"
            else:
                # Less than half → -10%
                agreement_bonus = -10
                agreement_level = "MIXED"

            confidence = base_confidence + agreement_bonus

            # ============================================
            # STEP 5: Special Pattern Bonuses
            # ============================================
            special_bonus = 0

            # RSI divergence bonus
            rsi_data = brain_results.get("RSI", {})
            if rsi_data:
                rsi_details = rsi_data.get("details", {})
                if rsi_details.get("divergence"):
                    special_bonus += 5
                    print("[ENGINE]   +5% RSI divergence bonus")

            # MACD crossover bonus
            macd_data = brain_results.get("MACD", {})
            if macd_data:
                macd_details = macd_data.get("details", {})
                macd_signal_str = macd_data.get("signal", "")
                if ("crossover" in str(macd_signal_str).lower() or
                        macd_details.get("crossover")):
                    special_bonus += 5
                    print("[ENGINE]   +5% MACD crossover bonus")

            # Bollinger squeeze bonus
            boll_data = brain_results.get("BOLLINGER", {})
            if boll_data:
                boll_details = boll_data.get("details", {})
                if boll_details.get("squeeze") or \
                        boll_details.get("squeeze_releasing"):
                    special_bonus += 5
                    print("[ENGINE]   +5% Bollinger squeeze bonus")

            # Volume spike bonus
            vol_data = brain_results.get("VOLUME", {})
            if vol_data:
                vol_details = vol_data.get("details", {})
                vol_signal = vol_data.get("signal", "")
                if ("spike" in str(vol_signal).lower() or
                        vol_details.get("volume_spike")):
                    special_bonus += 5
                    print("[ENGINE]   +5% Volume spike bonus")

            # OBV divergence bonus
            obv_data = brain_results.get("OBV", {})
            if obv_data:
                if obv_data.get("divergence"):
                    special_bonus += 5
                    print("[ENGINE]   +5% OBV divergence bonus")

            # Candlestick strong pattern bonus
            candle_data = brain_results.get("CANDLE_PATTERNS", {})
            if candle_data:
                candle_details = candle_data.get("details", {})
                strongest = candle_details.get(
                    "strongest_pattern", ""
                )
                if strongest in (
                    "BULLISH_ENGULFING", "BEARISH_ENGULFING",
                    "MORNING_STAR", "EVENING_STAR",
                    "THREE_WHITE_SOLDIERS", "THREE_BLACK_CROWS"
                ):
                    special_bonus += 5
                    print("[ENGINE]   +5% Strong candle "
                          "pattern bonus")

            confidence += special_bonus

            # ============================================
            # STEP 6: Cap at 95% (never say 100%)
            # ============================================
            confidence = max(0, min(95, confidence))

            # Neutral direction → 0 confidence
            if direction == "NEUTRAL":
                confidence = 0

            # ============================================
            # STEP 7: Quality Tier
            # ============================================
            if confidence >= TIER_STRONG:
                quality = "STRONG"
            elif confidence >= TIER_MODERATE:
                quality = "MODERATE"
            elif confidence >= TIER_WEAK:
                quality = "WEAK"
            else:
                quality = "NO_TRADE"

            tier_info = QUALITY_TIERS[quality]

            # ============================================
            # STEP 8: Calculate Trade Levels
            # ============================================
            levels = self._calculate_trade_levels(
                brain_results, direction, current_price
            )

            # ============================================
            # STEP 9: Build Final Signal
            # ============================================
            now = datetime.now()

            signal = {
                "pair": pair,
                "direction": direction,
                "confidence": round(confidence, 2),
                "quality": quality,
                "quality_emoji": tier_info["emoji"],
                "quality_label": tier_info["label"],
                "entry_price": levels["entry_price"],
                "target_1": levels["target_1"],
                "target_2": levels["target_2"],
                "stop_loss": levels["stop_loss"],
                "risk_reward": levels["risk_reward"],
                "weighted_score": round(weighted_score, 2),
                "agreement_level": agreement_level,
                "agreement_bonus": agreement_bonus,
                "special_bonus": special_bonus,
                "brains_agreeing": agreeing,
                "active_brains": active_brains,
                "long_votes": long_count,
                "short_votes": short_count,
                "neutral_votes": neutral_count,
                "brain_details": brain_details,
                "valid_for_minutes": self.scan_interval,
                "timestamp": now.strftime(DATE_FORMAT),
                "timeframe": "5m",
                "description": self._build_description(
                    direction, confidence, quality,
                    agreeing, active_brains, pair
                ),
            }

            return signal

        except Exception as e:
            print("[ENGINE] ❌ Combine signals error: {}".format(e))
            return self._build_no_trade_signal(
                pair, current_price, {}, 0, 0,
                "Analysis error: {}".format(e)
            )

    # ============================================
    # FUNCTION 6: CALCULATE TRADE LEVELS
    # ============================================

    def _calculate_trade_levels(self, brain_results,
                                 direction, current_price):
        """
        Calculate entry, targets, and stop loss.

        Uses ATR for volatility-adjusted levels.
        Checks S/R and Bollinger for smarter levels.
        Ensures minimum 1.5:1 risk/reward.

        For LONG:
          Entry = current price
          Target 1 = entry + 1.5 × ATR
          Target 2 = entry + 2.5 × ATR
          Stop Loss = entry - 1.0 × ATR

        For SHORT:
          Entry = current price
          Target 1 = entry - 1.5 × ATR
          Target 2 = entry - 2.5 × ATR
          Stop Loss = entry + 1.0 × ATR

        Smarter levels from Bollinger/S&R override
        if they provide better targets.

        Args:
            brain_results (dict): Brain outputs
            direction (str):      LONG or SHORT
            current_price (float): Latest close

        Returns:
            dict: {entry, target_1, target_2, stop_loss, rr}
        """
        try:
            if current_price <= 0 or direction == "NEUTRAL":
                return self._default_levels(current_price)

            # ------ Get ATR from Bollinger data ------
            atr = current_price * 0.015  # Default 1.5%

            boll_data = brain_results.get("BOLLINGER", {})
            if boll_data:
                details = boll_data.get("details", {})
                upper = details.get("upper_band", 0)
                lower = details.get("lower_band", 0)
                middle = details.get("middle_band", 0)

                if upper and lower and upper > lower:
                    bandwidth = upper - lower
                    atr = bandwidth / 4.0

            # Minimum ATR = 0.3% of price
            atr = max(atr, current_price * 0.003)

            # ------ Base levels ------
            entry_price = current_price

            if direction == "LONG":
                target_1 = entry_price + (1.5 * atr)
                target_2 = entry_price + (2.5 * atr)
                stop_loss = entry_price - (1.0 * atr)
            else:  # SHORT
                target_1 = entry_price - (1.5 * atr)
                target_2 = entry_price - (2.5 * atr)
                stop_loss = entry_price + (1.0 * atr)

            # ------ Smart levels from Bollinger ------
            if boll_data:
                details = boll_data.get("details", {})
                upper = details.get("upper_band", 0)
                lower = details.get("lower_band", 0)
                middle = details.get("middle_band", 0)

                if direction == "LONG" and upper and middle:
                    if middle > entry_price:
                        target_1 = min(target_1, middle)
                    if upper > target_1:
                        target_2 = upper

                    if lower and lower < entry_price:
                        better_stop = lower - (0.1 * atr)
                        if better_stop > stop_loss:
                            stop_loss = better_stop

                elif direction == "SHORT" and lower and middle:
                    if middle < entry_price:
                        target_1 = max(target_1, middle)
                    if lower < target_1:
                        target_2 = lower

                    if upper and upper > entry_price:
                        better_stop = upper + (0.1 * atr)
                        if better_stop < stop_loss:
                            stop_loss = better_stop

            # ------ Smart levels from S/R ------
            sr_data = brain_results.get("SUPPORT_RESISTANCE", {})
            if sr_data:
                details = sr_data.get("details", {})
                supports = details.get("support_levels", [])
                resistances = details.get("resistance_levels", [])

                if direction == "LONG":
                    if resistances:
                        above = [r for r in resistances
                                 if r > entry_price]
                        if above:
                            nearest_r = min(above)
                            if nearest_r < target_2:
                                target_2 = nearest_r

                    if supports:
                        below = [s for s in supports
                                 if s < entry_price]
                        if below:
                            nearest_s = max(below)
                            better = nearest_s - (0.1 * atr)
                            if better > stop_loss:
                                stop_loss = better

                elif direction == "SHORT":
                    if supports:
                        below = [s for s in supports
                                 if s < entry_price]
                        if below:
                            nearest_s = max(below)
                            if nearest_s > target_2:
                                target_2 = nearest_s

                    if resistances:
                        above = [r for r in resistances
                                 if r > entry_price]
                        if above:
                            nearest_r = min(above)
                            better = nearest_r + (0.1 * atr)
                            if better < stop_loss:
                                stop_loss = better

            # ------ Risk / Reward ------
            risk = abs(entry_price - stop_loss)
            reward = abs(target_1 - entry_price)

            if risk > 0:
                risk_reward = round(reward / risk, 2)
            else:
                risk_reward = 0

            # Enforce minimum 1.5 R:R
            if risk_reward < 1.5 and risk > 0:
                if direction == "LONG":
                    target_1 = entry_price + (risk * 1.5)
                else:
                    target_1 = entry_price - (risk * 1.5)
                risk_reward = 1.5

            # Ensure target_2 is beyond target_1
            if direction == "LONG":
                target_2 = max(target_2, target_1 + atr)
            else:
                target_2 = min(target_2, target_1 - atr)

            # ------ Round prices ------
            dec = self._get_decimals(entry_price)

            return {
                "entry_price": round(entry_price, dec),
                "target_1": round(target_1, dec),
                "target_2": round(target_2, dec),
                "stop_loss": round(stop_loss, dec),
                "risk_reward": risk_reward,
            }

        except Exception as e:
            print("[ENGINE] ❌ Trade levels error: {}".format(e))
            return self._default_levels(current_price)

    def _default_levels(self, price=0):
        """Return empty trade levels."""
        return {
            "entry_price": price,
            "target_1": 0,
            "target_2": 0,
            "stop_loss": 0,
            "risk_reward": 0,
        }

    def _get_decimals(self, price):
        """Get appropriate decimal places for a price."""
        if price >= 1000:
            return 2
        elif price >= 1:
            return 4
        elif price >= 0.01:
            return 5
        else:
            return 8

    # ============================================
    # FUNCTION 7: ANALYZE SINGLE PAIR
    # ============================================

    async def analyze_pair(self, pair):
        """
        Analyze a single trading pair.

        Pipeline:
        1. Fetch OHLCV data
        2. Run all 8 brains
        3. Combine into one signal
        4. Return signal with confidence

        Args:
            pair (str): Trading pair (e.g. "BTC/USDT")

        Returns:
            dict: Signal with confidence, or no-trade signal
        """
        try:
            print("[ENGINE]   📊 Analyzing {}...".format(pair))

            # ------ Fetch data ------
            df = None

            if data_fetcher:
                try:
                    symbol = pair.replace("/", "")
                    df = await data_fetcher.get_klines(
                        symbol=symbol,
                        interval="5m",
                        limit=100,
                    )
                except Exception as e:
                    print("[ENGINE]   ❌ Data fetch error "
                          "for {}: {}".format(pair, e))

            if df is None or df.empty:
                print("[ENGINE]   ⚠️ No data for {}".format(pair))
                return self._build_no_trade_signal(
                    pair, 0, {}, 0, 0, "No data available"
                )

            # Current price
            current_price = float(df["close"].iloc[-1])

            print("[ENGINE]   📈 {} candles | "
                  "Price: {:.2f}".format(len(df), current_price))

            # ------ Run all brains ------
            brain_results = self.run_all_brains(df)

            active = sum(
                1 for r in brain_results.values()
                if r is not None
            )

            print("[ENGINE]   🧠 {}/{} brains responded".format(
                active, len(self._brains)
            ))

            # ------ Combine into signal ------
            signal = self.combine_signals(
                brain_results, pair, current_price
            )

            return signal

        except Exception as e:
            print("[ENGINE] ❌ Analyze {} error: {}".format(pair, e))
            if bot_logger:
                bot_logger.log_error("ENGINE", e, tb_info=True)
            return self._build_no_trade_signal(
                pair, 0, {}, 0, 0, "Analysis error"
            )

    # ============================================
    # FUNCTION 8: SCAN AND PICK BEST (MAIN)
    # ============================================

    async def scan_and_pick_best(self):
        """
        THE MAIN FUNCTION — Scans all pairs and picks
        the single best signal.

        This is what runs every 10 minutes.

        Pipeline:
        ┌───────────────────────────────────────┐
        │ 1. Scan ALL 10 pairs                  │
        │ 2. Run 8 brains on EACH               │
        │ 3. Get confidence for each pair        │
        │ 4. RANK all pairs by confidence        │
        │ 5. Pick #1 best pair                   │
        │ 6. Return best signal OR no-trade msg  │
        └───────────────────────────────────────┘

        Returns:
            dict: {
                "has_signal": bool,
                "best_signal": dict or None,
                "all_results": list,
                "no_trade_message": str or None,
                "scan_time": str,
                "scan_duration": float,
            }
        """
        start_time = datetime.now()
        self._scan_count += 1

        print("\n" + "=" * 55)
        print("  🔍 SIGNAL ENGINE — SCAN #{}".format(
            self._scan_count
        ))
        print("  ⏰ {}".format(
            start_time.strftime("%Y-%m-%d %H:%M:%S")
        ))
        print("  📊 Scanning {} pairs × {} brains".format(
            len(self.trading_pairs), len(self._brains)
        ))
        print("=" * 55 + "\n")

        all_results = []

        try:
            # ============================================
            # STEP 1-3: Scan all pairs
            # ============================================
            for pair in self.trading_pairs:
                try:
                    signal = await self.analyze_pair(pair)

                    if signal:
                        all_results.append(signal)

                        quality = signal.get("quality", "NO_TRADE")
                        conf = signal.get("confidence", 0)
                        direction = signal.get("direction", "?")
                        emoji = signal.get("quality_emoji", "⚪")

                        print("[ENGINE] {} {} → {} {:.0f}% "
                              "({})".format(
                                  emoji, pair, direction,
                                  conf, quality
                              ))

                    # Small delay between pairs (avoid API spam)
                    await asyncio.sleep(0.5)

                except Exception as e:
                    print("[ENGINE] ❌ {} error: {}".format(pair, e))
                    continue

            # ============================================
            # STEP 4: Rank by confidence (descending)
            # ============================================
            all_results.sort(
                key=lambda x: x.get("confidence", 0),
                reverse=True,
            )

            # ============================================
            # STEP 5: Pick #1 best
            # ============================================
            duration = (
                datetime.now() - start_time
            ).total_seconds()

            # Print rankings
            print("\n[ENGINE] ━━━ RANKINGS ━━━")
            for i, sig in enumerate(all_results):
                emoji = sig.get("quality_emoji", "⚪")
                pair = sig.get("pair", "?")
                conf = sig.get("confidence", 0)
                direction = sig.get("direction", "?")
                quality = sig.get("quality", "?")

                marker = " ← BEST 🏆" if i == 0 else ""

                print("[ENGINE]   #{} {} {} → {} "
                      "{:.0f}% ({}){}".format(
                          i + 1, emoji, pair, direction,
                          conf, quality, marker
                      ))

            if not all_results:
                # No results at all
                return self._build_scan_result(
                    has_signal=False,
                    best_signal=None,
                    all_results=[],
                    no_trade_msg=self._build_no_trade_message(
                        "No data available for any pair", None
                    ),
                    duration=duration,
                )

            best = all_results[0]
            best_conf = best.get("confidence", 0)
            best_quality = best.get("quality", "NO_TRADE")

            # ============================================
            # STEP 6: Decide — signal or no-trade
            # ============================================

            if best_quality == "NO_TRADE" or best_conf < TIER_WEAK:
                # Market is choppy — no good trade
                self._no_trade_count += 1

                no_trade_msg = self._build_no_trade_message(
                    "Market is choppy. No strong signal found.",
                    best,
                )

                print("\n[ENGINE] 🔴 NO TRADE — Best was "
                      "{} at {:.0f}%".format(
                          best.get("pair", "?"), best_conf
                      ))
                print("[ENGINE]    Scan #{} complete in "
                      "{:.1f}s\n".format(
                          self._scan_count, duration
                      ))

                if bot_logger:
                    bot_logger.info(
                        "No trade — best: {} at {:.0f}%".format(
                            best.get("pair", "?"), best_conf
                        ),
                        module="ENGINE",
                    )

                return self._build_scan_result(
                    has_signal=False,
                    best_signal=best,
                    all_results=all_results,
                    no_trade_msg=no_trade_msg,
                    duration=duration,
                )

            else:
                # We have a signal!
                self._signal_count += 1
                self._last_signals[best["pair"]] = best

                print("\n[ENGINE] ✅ SIGNAL: {} {} at "
                      "{:.0f}% ({})".format(
                          best.get("pair", "?"),
                          best.get("direction", "?"),
                          best_conf,
                          best_quality,
                      ))
                print("[ENGINE]    Entry: {} | T1: {} | "
                      "T2: {} | SL: {}".format(
                          best.get("entry_price", 0),
                          best.get("target_1", 0),
                          best.get("target_2", 0),
                          best.get("stop_loss", 0),
                      ))
                print("[ENGINE]    R/R: {} | Agreement: "
                      "{}".format(
                          best.get("risk_reward", 0),
                          best.get("agreement_level", "?"),
                      ))
                print("[ENGINE]    Signal #{} | Scan #{} | "
                      "{:.1f}s\n".format(
                          self._signal_count,
                          self._scan_count, duration
                      ))

                if bot_logger:
                    bot_logger.log_signal(best)

                if performance_tracker:
                    try:
                        sig_id = performance_tracker.log_new_signal(
                            best
                        )
                        best["signal_id"] = sig_id
                    except Exception:
                        pass

                return self._build_scan_result(
                    has_signal=True,
                    best_signal=best,
                    all_results=all_results,
                    no_trade_msg=None,
                    duration=duration,
                )

        except Exception as e:
            duration = (
                datetime.now() - start_time
            ).total_seconds()
            print("[ENGINE] ❌ Scan error: {}".format(e))
            if bot_logger:
                bot_logger.log_error("ENGINE", e, tb_info=True)

            return self._build_scan_result(
                has_signal=False,
                best_signal=None,
                all_results=all_results,
                no_trade_msg=self._build_no_trade_message(
                    "Scan error occurred", None
                ),
                duration=duration,
            )

    def _build_scan_result(self, has_signal, best_signal,
                            all_results, no_trade_msg, duration):
        """Build standardized scan result dict."""
        return {
            "has_signal": has_signal,
            "best_signal": best_signal,
            "all_results": all_results,
            "no_trade_message": no_trade_msg,
            "scan_number": self._scan_count,
            "signal_number": self._signal_count,
            "scan_time": datetime.now().strftime(DATE_FORMAT),
            "scan_duration_seconds": round(duration, 2),
            "pairs_scanned": len(all_results),
        }

    # ============================================
    # FUNCTION 9: NO-TRADE MESSAGE
    # ============================================

    def _build_no_trade_message(self, reason, best_signal):
        """
        Build honest "no trade" message.

        This builds TRUST with users — not every
        10 minutes will have a trade, and that's
        REALISTIC.

        Args:
            reason (str):       Why no trade
            best_signal (dict): Best pair info (if any)

        Returns:
            str: Formatted no-trade message
        """
        try:
            best_info = ""
            if best_signal:
                best_info = (
                    "\n📊 Best opportunity was "
                    "<b>{pair}</b> at "
                    "<b>{conf:.0f}%</b> confidence"
                    "\n   (below our {min}% minimum "
                    "for trading)"
                ).format(
                    pair=best_signal.get("pair", "?"),
                    conf=best_signal.get("confidence", 0),
                    min=TIER_WEAK,
                )

            msg = (
                "🔴 <b>⏸ No Strong Signal Found</b>\n"
                "\n"
                "{reason}\n"
                "{best_info}\n"
                "\n"
                "💡 <i>The market is choppy right now. "
                "Skipping this round is the smart move — "
                "protecting your capital is priority #1.</i>\n"
                "\n"
                "⏰ Next scan in <b>{interval} minutes</b>\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━"
            ).format(
                reason=reason,
                best_info=best_info,
                interval=self.scan_interval,
            )

            return msg

        except Exception:
            return (
                "🔴 ⏸ No strong signal found.\n"
                "Next scan in {} minutes.".format(
                    self.scan_interval
                )
            )

    def _build_no_trade_signal(self, pair, price,
                                brain_details, active,
                                confidence, reason):
        """Build a no-trade signal dict for ranking."""
        return {
            "pair": pair,
            "direction": "NEUTRAL",
            "confidence": confidence,
            "quality": "NO_TRADE",
            "quality_emoji": "🔴",
            "quality_label": "NO TRADE",
            "entry_price": price,
            "target_1": 0,
            "target_2": 0,
            "stop_loss": 0,
            "risk_reward": 0,
            "weighted_score": 50,
            "agreement_level": "MIXED",
            "agreement_bonus": 0,
            "special_bonus": 0,
            "brains_agreeing": 0,
            "active_brains": active,
            "long_votes": 0,
            "short_votes": 0,
            "neutral_votes": active,
            "brain_details": brain_details,
            "valid_for_minutes": self.scan_interval,
            "timestamp": datetime.now().strftime(DATE_FORMAT),
            "timeframe": "5m",
            "description": reason,
        }

    # ============================================
    # FUNCTION 10: DESCRIPTION BUILDER
    # ============================================

    def _build_description(self, direction, confidence,
                            quality, agreeing, active, pair):
        """Build human-readable signal description."""
        try:
            if quality == "STRONG":
                strength = "Strong"
            elif quality == "MODERATE":
                strength = "Moderate"
            elif quality == "WEAK":
                strength = "Weak"
            else:
                return "No clear trading opportunity"

            dir_word = "buy" if direction == "LONG" else "sell"

            return (
                "{} {} signal — {}/{} indicators "
                "agree on {}".format(
                    strength, dir_word, agreeing,
                    active, pair
                )
            )

        except Exception:
            return "Trading signal generated"

    # ============================================
    # FUNCTION 11: CONTINUOUS SCAN LOOP
    # ============================================

    async def run_continuous_scan(self, on_signal_callback=None,
                                   on_no_trade_callback=None):
        """
        Run the scan loop forever — every 10 minutes.

        This is the 24/7 heartbeat of the bot.

        Every cycle:
        1. Run scan_and_pick_best()
        2. If signal → call on_signal_callback(signal)
        3. If no trade → call on_no_trade_callback(message)
        4. Wait scan_interval minutes
        5. Repeat forever

        Args:
            on_signal_callback:     async func(signal_dict)
            on_no_trade_callback:   async func(message_str)
        """
        print("\n[ENGINE] 🔄 Starting continuous scan loop")
        print("[ENGINE]    Interval: {} minutes".format(
            self.scan_interval
        ))
        print("[ENGINE]    Pairs: {}".format(
            len(self.trading_pairs)
        ))
        print("[ENGINE]    Press Ctrl+C to stop\n")

        while True:
            try:
                # Run scan
                result = await self.scan_and_pick_best()

                if result["has_signal"] and result["best_signal"]:
                    # We have a signal!
                    if on_signal_callback:
                        try:
                            await on_signal_callback(
                                result["best_signal"]
                            )
                        except Exception as e:
                            print("[ENGINE] ❌ Signal callback "
                                  "error: {}".format(e))

                else:
                    # No trade — send choppy market message
                    if on_no_trade_callback:
                        no_trade_msg = result.get(
                            "no_trade_message",
                            "⏸ No signal this round."
                        )
                        try:
                            await on_no_trade_callback(
                                no_trade_msg
                            )
                        except Exception as e:
                            print("[ENGINE] ❌ No-trade callback "
                                  "error: {}".format(e))

                # Wait for next scan
                wait_seconds = self.scan_interval * 60
                print("[ENGINE] ⏳ Next scan in {} "
                      "minutes...".format(self.scan_interval))

                await asyncio.sleep(wait_seconds)

            except asyncio.CancelledError:
                print("[ENGINE] 🛑 Scan loop cancelled")
                break

            except KeyboardInterrupt:
                print("[ENGINE] 🛑 Scan loop stopped by user")
                break

            except Exception as e:
                print("[ENGINE] ❌ Scan loop error: {}".format(e))
                if bot_logger:
                    bot_logger.log_error("ENGINE", e, tb_info=True)

                # Wait before retry
                print("[ENGINE] ⏳ Retrying in 60 seconds...")
                await asyncio.sleep(60)

    # ============================================
    # FUNCTION 12: STATISTICS
    # ============================================

    def get_stats(self):
        """Get engine statistics."""
        return {
            "active_brains": len(self._brains),
            "brain_names": list(self._brains.keys()),
            "brain_weights": self.brain_weights,
            "total_signals": self._signal_count,
            "total_scans": self._scan_count,
            "no_trade_count": self._no_trade_count,
            "trading_pairs": len(self.trading_pairs),
            "cached_signals": len(self._last_signals),
            "scan_interval": self.scan_interval,
        }

    def get_last_signal(self, pair=None):
        """
        Get last signal for a pair, or most recent overall.

        Args:
            pair (str, optional): Specific pair

        Returns:
            dict or None: Last signal
        """
        if pair:
            return self._last_signals.get(pair)

        if self._last_signals:
            return max(
                self._last_signals.values(),
                key=lambda x: x.get("timestamp", ""),
            )
        return None


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

signal_engine = SignalEngine()

print("[ENGINE] ✅ Signal Engine loaded and ready")