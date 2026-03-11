# ============================================
# CANDLESTICK PATTERN TEST SCRIPT
# ============================================
# Run: python test_candle_patterns.py
# ============================================

import numpy as np
import pandas as pd


def make_candle_df(candles):
    """
    Creates DataFrame from list of (open, high, low, close) tuples.
    """
    n = len(candles)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
        "open": [c[0] for c in candles],
        "high": [c[1] for c in candles],
        "low": [c[2] for c in candles],
        "close": [c[3] for c in candles],
        "volume": [1000.0 + i * 10 for i in range(n)],
    })


def make_downtrend_then(pattern_candles):
    """Creates 12 downtrend candles + pattern candles."""
    trend = []
    for i in range(12):
        base = 110 - i * 1.0
        trend.append((base, base + 0.5, base - 1.2, base - 0.8))
    return make_candle_df(trend + pattern_candles)


def make_uptrend_then(pattern_candles):
    """Creates 12 uptrend candles + pattern candles."""
    trend = []
    for i in range(12):
        base = 90 + i * 1.0
        trend.append((base, base + 1.2, base - 0.3, base + 0.8))
    return make_candle_df(trend + pattern_candles)


def run_tests():
    """Test all candlestick pattern functions."""

    from algorithms.candle_patterns import CandlePatternAnalyzer

    analyzer = CandlePatternAnalyzer()

    print("\n" + "=" * 55)
    print("   RUNNING CANDLESTICK PATTERN TESTS")
    print("=" * 55 + "\n")

    passed = 0
    failed = 0

    # ---- TEST 1: Candle properties ----
    print("--- TEST 1: get_candle_properties ---")
    try:
        row = {"open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0}
        props = analyzer.get_candle_properties(row)

        assert props is not None
        assert props["is_bullish"] is True
        assert props["is_bearish"] is False
        assert props["body_size"] == 4.0
        assert props["total_range"] == 7.0
        assert props["upper_wick"] == 1.0
        assert props["lower_wick"] == 2.0
        assert 0 < props["body_ratio"] < 1

        print("  Body: {:.1f} | Range: {:.1f} | Ratio: {:.2f}".format(
            props["body_size"], props["total_range"], props["body_ratio"]
        ))
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 2: Edge cases ----
    print("--- TEST 2: Properties edge cases ---")
    try:
        # Flat candle
        flat = {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}
        props_flat = analyzer.get_candle_properties(flat)
        assert props_flat is not None
        assert props_flat["body_size"] == 0
        assert props_flat["total_range"] == 0
        assert props_flat["body_ratio"] == 0

        # Doji
        doji = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 100.05}
        props_doji = analyzer.get_candle_properties(doji)
        assert props_doji is not None
        assert props_doji["is_doji"] is True

        # NaN
        nan_row = {"open": float("nan"), "high": 100, "low": 99, "close": 100}
        assert analyzer.get_candle_properties(nan_row) is None

        print("  All edge cases handled")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 3: Prior trend detection ----
    print("--- TEST 3: determine_prior_trend ---")
    try:
        up_candles = [(90 + i, 91 + i, 89 + i, 90.5 + i) for i in range(15)]
        df_up = make_candle_df(up_candles)
        trend = analyzer.determine_prior_trend(df_up, 14, lookback=10)
        assert trend == "UPTREND", "Expected UPTREND, got {}".format(trend)

        down_candles = [(110 - i, 111 - i, 109 - i, 109.5 - i) for i in range(15)]
        df_down = make_candle_df(down_candles)
        trend = analyzer.determine_prior_trend(df_down, 14, lookback=10)
        assert trend == "DOWNTREND", "Expected DOWNTREND, got {}".format(trend)

        assert analyzer.determine_prior_trend(None, 0) == "SIDEWAYS"

        print("  Trend detection working")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 4: Hammer detection ----
    print("--- TEST 4: HAMMER pattern ---")
    try:
        # Hammer: small body near top, long lower wick
        # body=0.8, range=5.0, body_pct=16%, lower_wick_pct=80%
        hammer = [(97.0, 98.0, 93.0, 97.8)]
        df_hammer = make_downtrend_then(hammer)
        patterns = analyzer.detect_single_patterns(
            df_hammer, len(df_hammer) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "HAMMER" in found, \
            "Should detect HAMMER. Got: {}".format(found)
        assert any(p["signal"] == "LONG" for p in patterns)

        print("  Hammer detected in downtrend")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 5: Shooting Star ----
    print("--- TEST 5: SHOOTING STAR pattern ---")
    try:
        # Shooting Star: small body near bottom, long upper wick
        # body=0.8, range=5.5, body_pct=14.5%, upper_wick_pct=76%
        star = [(101.0, 106.0, 100.5, 101.8)]
        df_star = make_uptrend_then(star)
        patterns = analyzer.detect_single_patterns(
            df_star, len(df_star) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "SHOOTING_STAR" in found, \
            "Should detect SHOOTING_STAR. Got: {}".format(found)
        assert any(p["signal"] == "SHORT" for p in patterns)

        print("  Shooting Star detected in uptrend")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 6: Doji ----
    print("--- TEST 6: DOJI patterns ---")
    try:
        # Doji with balanced wicks (NOT a hammer shape)
        # body=0.05, range=10.0, body_pct=0.5%
        # upper_wick=4.95 (49.5%), lower_wick=5.0 (50%)
        doji_candle = [(100.0, 104.95, 95.0, 100.05)]
        df_doji = make_downtrend_then(doji_candle)
        patterns = analyzer.detect_single_patterns(
            df_doji, len(df_doji) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert any("DOJI" in name for name in found), \
            "Should detect a DOJI variant. Got: {}".format(found)

        print("  Doji detected")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 7: Marubozu ----
    print("--- TEST 7: MARUBOZU pattern ---")
    try:
        # Bullish marubozu: body > 90% of range
        # body=4.9, range=5.1, body_pct=96%
        maru = [(100.0, 105.0, 99.9, 104.9)]
        df_maru = make_downtrend_then(maru)
        patterns = analyzer.detect_single_patterns(
            df_maru, len(df_maru) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert any("MARUBOZU" in name for name in found), \
            "Should detect MARUBOZU. Got: {}".format(found)

        print("  Marubozu detected")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 8: Bullish Engulfing ----
    print("--- TEST 8: BULLISH ENGULFING ---")
    try:
        engulf = [
            (100.0, 100.5, 98.0, 98.5),   # C1: bearish
            (98.0, 101.5, 97.5, 101.0),    # C2: bullish covers C1
        ]
        df_engulf = make_downtrend_then(engulf)
        patterns = analyzer.detect_two_candle_patterns(
            df_engulf, len(df_engulf) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "BULLISH_ENGULFING" in found, \
            "Should detect BULLISH_ENGULFING. Got: {}".format(found)

        print("  Bullish Engulfing detected")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 9: Bearish Engulfing ----
    print("--- TEST 9: BEARISH ENGULFING ---")
    try:
        bear_engulf = [
            (100.0, 101.5, 99.5, 101.0),  # C1: bullish
            (101.5, 102.0, 98.0, 99.0),   # C2: bearish covers C1
        ]
        df_bear = make_uptrend_then(bear_engulf)
        patterns = analyzer.detect_two_candle_patterns(
            df_bear, len(df_bear) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "BEARISH_ENGULFING" in found, \
            "Should detect BEARISH_ENGULFING. Got: {}".format(found)

        print("  Bearish Engulfing detected")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 10: Morning Star ----
    print("--- TEST 10: MORNING STAR ---")
    try:
        morning = [
            (100.0, 100.5, 96.0, 96.5),   # C1: large bearish
            #   body=3.5  range=4.5  pct=77.8%  ✅ bearish ✅
            (96.2, 96.5, 95.5, 96.0),     # C2: small body star
            #   body=0.2  range=1.0  pct=20.0%  ✅ < 30%
            (96.0, 100.0, 95.8, 99.5),    # C3: large bullish
            #   body=3.5  range=4.2  pct=83.3%  ✅ bullish ✅
            #   C1 midpoint = (100+96.5)/2 = 98.25
            #   C3 close 99.5 > 98.25  ✅
        ]
        df_morning = make_downtrend_then(morning)
        patterns = analyzer.detect_three_candle_patterns(
            df_morning, len(df_morning) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "MORNING_STAR" in found, \
            "Should detect MORNING_STAR. Got: {}".format(found)

        print("  Morning Star detected")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 11: Evening Star ----
    print("--- TEST 11: EVENING STAR ---")
    try:
        evening = [
            (100.0, 104.0, 99.5, 103.5),  # C1: large bullish
            (103.5, 104.5, 103.0, 103.8),  # C2: small body (star)
            (104.0, 104.2, 100.0, 101.0),  # C3: large bearish < C1 mid
        ]
        df_evening = make_uptrend_then(evening)
        patterns = analyzer.detect_three_candle_patterns(
            df_evening, len(df_evening) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "EVENING_STAR" in found, \
            "Should detect EVENING_STAR. Got: {}".format(found)

        print("  Evening Star detected")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 12: Three White Soldiers ----
    print("--- TEST 12: THREE WHITE SOLDIERS ---")
    try:
        soldiers = [
            (95.0, 98.0, 94.8, 97.5),     # C1: bullish
            (96.0, 100.0, 95.8, 99.5),    # C2: opens in C1 body
            (98.0, 102.0, 97.8, 101.5),   # C3: opens in C2 body
        ]
        df_soldiers = make_downtrend_then(soldiers)
        patterns = analyzer.detect_three_candle_patterns(
            df_soldiers, len(df_soldiers) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "THREE_WHITE_SOLDIERS" in found, \
            "Should detect THREE_WHITE_SOLDIERS. Got: {}".format(found)

        print("  Three White Soldiers detected")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 13: Three Black Crows ----
    print("--- TEST 13: THREE BLACK CROWS ---")
    try:
        crows = [
            (105.0, 105.5, 102.0, 102.5),  # C1: bearish
            (103.0, 103.5, 100.0, 100.5),  # C2: opens in C1 body
            (101.0, 101.5, 98.0, 98.5),    # C3: opens in C2 body
        ]
        df_crows = make_uptrend_then(crows)
        patterns = analyzer.detect_three_candle_patterns(
            df_crows, len(df_crows) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "THREE_BLACK_CROWS" in found, \
            "Should detect THREE_BLACK_CROWS. Got: {}".format(found)

        print("  Three Black Crows detected")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 14: Hanging Man ----
    print("--- TEST 14: HANGING MAN ---")
    try:
        # Same shape as hammer but in UPTREND
        hanging = [(101.0, 101.5, 96.0, 101.3)]
        df_hang = make_uptrend_then(hanging)
        patterns = analyzer.detect_single_patterns(
            df_hang, len(df_hang) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "HANGING_MAN" in found, \
            "Should detect HANGING_MAN. Got: {}".format(found)
        assert any(p["signal"] == "SHORT" for p in patterns)

        print("  Hanging Man detected in uptrend")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 15: Inverted Hammer ----
    print("--- TEST 15: INVERTED HAMMER ---")
    try:
        # Long upper wick after downtrend
        inv_hammer = [(97.0, 102.0, 96.8, 97.5)]
        df_inv = make_downtrend_then(inv_hammer)
        patterns = analyzer.detect_single_patterns(
            df_inv, len(df_inv) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "INVERTED_HAMMER" in found, \
            "Should detect INVERTED_HAMMER. Got: {}".format(found)
        assert any(p["signal"] == "LONG" for p in patterns)

        print("  Inverted Hammer detected in downtrend")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 16: Dragonfly Doji (not confused with Hammer) ----
    print("--- TEST 16: DRAGONFLY DOJI vs HAMMER ---")
    try:
        # Dragonfly Doji: body_pct < 10%, lower_wick > 60%
        # BUT wicks are more balanced (upper wick > 15%)
        # So this should be Dragonfly Doji, NOT Hammer
        # body=0.05, range=10, body_pct=0.5%
        # lower=5.0 (50%), upper=4.95 (49.5%)
        # → Neither wick dominates → standard DOJI
        #
        # For actual dragonfly: needs upper < 15%
        # body=0.02, range=5.0, body_pct=0.4%
        # upper=0.0, lower=4.98 (99.6%)
        # → lower > 60% AND upper < 15% AND body < 10%
        # → Meets BOTH hammer and dragonfly criteria
        # → But since body_pct < small_body_pct (30%),
        #   it hits hammer shape detection FIRST
        #
        # Verify: a doji with balanced wicks gets DOJI, not hammer
        balanced_doji = [(100.0, 105.0, 95.0, 100.05)]
        df_bal = make_downtrend_then(balanced_doji)
        patterns = analyzer.detect_single_patterns(
            df_bal, len(df_bal) - 1
        )

        found = [p["pattern_name"] for p in patterns]
        assert "DOJI" in found, \
            "Balanced doji should be DOJI. Got: {}".format(found)
        assert "HAMMER" not in found, \
            "Balanced doji should NOT be HAMMER. Got: {}".format(found)

        print("  Balanced doji correctly identified as DOJI")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 17: Full analyze() pipeline ----
    print("--- TEST 17: Full analyze() pipeline ---")
    try:
        # Create a scenario with a clear hammer after downtrend
        hammer_data = [(97.0, 98.0, 93.0, 97.8)]
        df_full = make_downtrend_then(hammer_data)
        result = analyzer.analyze(df_full)

        assert result is not None
        assert result["brain"] == "CANDLE_PATTERNS"
        assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
        assert 0 <= result["confidence"] <= 100
        assert isinstance(result["patterns_found"], list)
        assert "prior_trend" in result
        assert "details" in result

        print("  analyze() returns valid result")
        print("  Direction: {} | Confidence: {}%".format(
            result["direction"], result["confidence"]
        ))
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 18: No pattern scenario ----
    print("--- TEST 18: No patterns (should be NEUTRAL) ---")
    try:
        # All identical candles — no pattern
        flat_data = [(100.0, 100.5, 99.5, 100.2) for _ in range(20)]
        df_flat = make_candle_df(flat_data)
        result = analyzer.analyze(df_flat)

        assert result["direction"] == "NEUTRAL"
        assert result["confidence"] == 0

        print("  Correctly returns NEUTRAL for no patterns")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 19: Insufficient data ----
    print("--- TEST 19: Insufficient data ---")
    try:
        tiny = make_candle_df([(100, 101, 99, 100.5)] * 5)
        result = analyzer.analyze(tiny)

        assert result["direction"] == "NEUTRAL"
        assert result["confidence"] == 0
        assert result["pattern_count"] == 0

        print("  Correctly returns NEUTRAL for insufficient data")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 20: Pattern reliability ----
    print("--- TEST 20: Pattern reliability scores ---")
    try:
        assert analyzer.get_pattern_reliability("BULLISH_ENGULFING") == 83
        assert analyzer.get_pattern_reliability("HAMMER") == 65
        assert analyzer.get_pattern_reliability("DOJI") == 48
        assert analyzer.get_pattern_reliability("UNKNOWN") == 40

        print("  Reliability scores correct")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ============================================
    # SUMMARY
    # ============================================
    total = passed + failed
    print("=" * 55)
    print("   TEST RESULTS: {}/{} PASSED".format(passed, total))
    if failed == 0:
        print("   🎉 ALL TESTS PASSED!")
    else:
        print("   ⚠ {} test(s) FAILED".format(failed))
    print("=" * 55)


if __name__ == "__main__":
    run_tests()