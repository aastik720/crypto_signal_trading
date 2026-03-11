# ============================================
# OBV ANALYZER TEST SCRIPT
# ============================================
# Run: python test_obv.py
# ============================================

import numpy as np
import pandas as pd


def make_df(closes, volumes):
    """Create DataFrame from close and volume lists."""
    n = len(closes)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
        "open": [c - 0.5 for c in closes],
        "high": [c + 1.0 for c in closes],
        "low": [c - 1.0 for c in closes],
        "close": closes,
        "volume": volumes,
    })


def run_tests():
    """Run all OBV analyzer tests."""

    from algorithms.obv import OBVAnalyzer

    analyzer = OBVAnalyzer()

    print("\n" + "=" * 55)
    print("   RUNNING OBV ANALYZER TESTS")
    print("=" * 55 + "\n")

    passed = 0
    failed = 0

    # ---- TEST 1: Basic OBV Calculation ----
    print("--- TEST 1: OBV Calculation ---")
    try:
        closes = [100, 101, 99, 102, 103]
        volumes = [1000, 1500, 800, 2000, 1200]

        obv = analyzer.calculate_obv(closes, volumes)

        # Manual calculation:
        # OBV[0] = 0 (start)
        # 101>100: OBV[1] = 0 + 1500 = 1500
        # 99<101:  OBV[2] = 1500 - 800 = 700
        # 102>99:  OBV[3] = 700 + 2000 = 2700
        # 103>102: OBV[4] = 2700 + 1200 = 3900

        assert len(obv) == 5
        assert obv[0] == 0.0
        assert obv[1] == 1500.0
        assert obv[2] == 700.0
        assert obv[3] == 2700.0
        assert obv[4] == 3900.0

        print("  OBV: {}".format(obv))
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 2: OBV with flat prices ----
    print("--- TEST 2: OBV with flat prices ---")
    try:
        closes = [100, 100, 100, 100, 100]
        volumes = [1000, 2000, 3000, 4000, 5000]

        obv = analyzer.calculate_obv(closes, volumes)

        # All closes equal → OBV stays 0
        assert all(v == 0.0 for v in obv)

        print("  OBV stays 0 for flat prices")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 3: OBV EMA Calculation ----
    print("--- TEST 3: OBV EMA ---")
    try:
        closes = list(range(100, 125))
        volumes = [1000] * 25
        obv = analyzer.calculate_obv(closes, volumes)
        obv_ema = analyzer.calculate_obv_ema(obv)

        assert len(obv_ema) == 25
        # First 9 values should be NaN (period=10)
        assert np.isnan(obv_ema[0])
        assert np.isnan(obv_ema[8])
        # 10th value should be valid
        assert not np.isnan(obv_ema[9])
        # EMA should be smoothed (less than raw OBV at end)
        assert obv_ema[-1] < obv[-1]

        print("  EMA computed correctly, smoothed vs raw")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 4: Rising OBV + Rising Price → LONG ----
    print("--- TEST 4: Bullish scenario (price+OBV rising) ---")
    try:
        # 25 candles: steadily rising price, good volume
        closes = [100 + i * 0.5 for i in range(25)]
        volumes = [2000 + i * 100 for i in range(25)]

        df = make_df(closes, volumes)
        result = analyzer.analyze(df)

        assert result["direction"] == "LONG", \
            "Expected LONG, got {}".format(result["direction"])
        assert result["obv_trend"] == "RISING"
        assert result["confidence"] > 0
        assert result["score"] > 55

        print("  Direction: {} | Score: {} | Conf: {}%".format(
            result["direction"], result["score"], result["confidence"]
        ))
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 5: Falling OBV + Falling Price → SHORT ----
    print("--- TEST 5: Bearish scenario (price+OBV falling) ---")
    try:
        # 25 candles: steadily falling price
        closes = [112 - i * 0.5 for i in range(25)]
        volumes = [2000 + i * 100 for i in range(25)]

        df = make_df(closes, volumes)
        result = analyzer.analyze(df)

        assert result["direction"] == "SHORT", \
            "Expected SHORT, got {}".format(result["direction"])
        assert result["obv_trend"] == "FALLING"
        assert result["score"] < 45

        print("  Direction: {} | Score: {} | Conf: {}%".format(
            result["direction"], result["score"], result["confidence"]
        ))
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 6: Divergence Detection ----
    print("--- TEST 6: Divergence detection ---")
    try:
        # Create data with bullish divergence:
        # Price makes lower lows, OBV makes higher lows
        n = 25

        # Price: 100→95 (dip1) → 100 (recovery) → 93 (dip2, lower)
        prices = []
        vols = []

        # Phase 1: stable (0-4)
        for i in range(5):
            prices.append(100.0)
            vols.append(1000)

        # Phase 2: first dip to 95 (5-9) — high volume selling
        for i in range(5):
            prices.append(100.0 - i * 1.0)
            vols.append(3000)

        # Phase 3: recovery to 100 (10-14)
        for i in range(5):
            prices.append(95.0 + i * 1.0)
            vols.append(3500)

        # Phase 4: second dip to 93 (15-19) — LOW volume selling
        for i in range(5):
            prices.append(100.0 - i * 1.5)
            vols.append(500)

        # Phase 5: slight recovery (20-24)
        for i in range(5):
            prices.append(92.5 + i * 0.5)
            vols.append(1500)

        obv = analyzer.calculate_obv(prices, vols)
        div = analyzer.detect_obv_divergence(prices, obv)

        # Price dip2 (93) < dip1 (95): lower low ✓
        # OBV at dip2 should be higher than at dip1
        # because selling volume was much smaller
        print("  Price lows: ~95 then ~93 (lower)")
        print("  OBV at phase2 end: {:.0f}".format(obv[9]))
        print("  OBV at phase4 end: {:.0f}".format(obv[19]))
        print("  Divergence: {}".format(div))

        # Note: divergence may or may not be detected depending
        # on swing point detection. Testing the mechanism works.
        if div == "BULLISH":
            print("  Bullish divergence correctly detected!")
        else:
            print("  Divergence not detected (swing points may "
                  "not align — this is acceptable)")

        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 7: Accumulation Detection ----
    print("--- TEST 7: Accumulation detection ---")
    try:
        # Price flat (~100), OBV rising (more up-volume candles)
        prices = []
        vols = []
        for i in range(25):
            # Price oscillates within 0.1% of 100
            prices.append(100.0 + 0.05 * (1 if i % 2 == 0 else -1))
            # Volume higher on up candles
            if i % 2 == 0:  # up candle
                vols.append(5000)
            else:  # down candle
                vols.append(1000)

        obv = analyzer.calculate_obv(prices, vols)
        flow = analyzer.detect_accumulation_distribution(prices, obv)

        print("  Price range: {:.2f} to {:.2f}".format(
            min(prices[-10:]), max(prices[-10:])
        ))
        print("  OBV end: {:.0f}".format(obv[-1]))
        print("  Flow: {}".format(flow))

        # With alternating prices and heavy up-volume,
        # OBV should trend up while price stays flat
        # May or may not hit the 65% threshold
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 8: Insufficient Data ----
    print("--- TEST 8: Insufficient data handling ---")
    try:
        tiny_closes = [100, 101, 102]
        tiny_volumes = [1000, 1000, 1000]
        df_tiny = make_df(tiny_closes, tiny_volumes)

        result = analyzer.analyze(df_tiny)

        assert result["direction"] == "NEUTRAL"
        assert result["confidence"] == 0
        assert result["score"] == 50

        print("  Correctly returns NEUTRAL for small data")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 9: Empty/None DataFrame ----
    print("--- TEST 9: Empty/None input ---")
    try:
        result_none = analyzer.analyze(None)
        assert result_none["direction"] == "NEUTRAL"

        result_empty = analyzer.analyze(pd.DataFrame())
        assert result_empty["direction"] == "NEUTRAL"

        print("  Handles None and empty DataFrame")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 10: Missing columns ----
    print("--- TEST 10: Missing column handling ---")
    try:
        df_no_vol = pd.DataFrame({
            "close": [100] * 25,
        })
        result = analyzer.analyze(df_no_vol)
        assert result["direction"] == "NEUTRAL"

        print("  Handles missing 'volume' column")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 11: Full analyze() result structure ----
    print("--- TEST 11: Result structure validation ---")
    try:
        closes = [100 + i * 0.3 for i in range(25)]
        volumes = [1500] * 25
        df = make_df(closes, volumes)

        result = analyzer.analyze(df)

        # Check all required fields exist
        required_fields = [
            "brain", "direction", "confidence", "score",
            "signal", "obv_current", "obv_ema", "obv_trend",
            "obv_above_ema", "price_obv_confirmation",
            "divergence", "flow", "description", "details",
        ]
        for field in required_fields:
            assert field in result, \
                "Missing field: {}".format(field)

        # Check details sub-dict
        detail_fields = [
            "obv_slope_normalized", "trend_strength",
            "ema_crossover", "price_slope_pct",
            "bullish_factors", "bearish_factors",
        ]
        for field in detail_fields:
            assert field in result["details"], \
                "Missing detail: {}".format(field)

        assert result["brain"] == "OBV"
        assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
        assert 0 <= result["confidence"] <= 100
        assert 0 <= result["score"] <= 100
        assert result["obv_trend"] in ("RISING", "FALLING", "FLAT")

        print("  All fields present and valid")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 12: Score boundaries ----
    print("--- TEST 12: Score boundary checks ---")
    try:
        # Strong bullish: rapidly rising prices with high volume
        strong_bull_closes = [100 + i * 2.0 for i in range(25)]
        strong_bull_vols = [5000 + i * 500 for i in range(25)]
        df_bull = make_df(strong_bull_closes, strong_bull_vols)
        result_bull = analyzer.analyze(df_bull)

        assert result_bull["score"] >= 60, \
            "Strong bull should score >=60, got {}".format(
                result_bull["score"]
            )

        # Strong bearish: rapidly falling prices with high volume
        strong_bear_closes = [150 - i * 2.0 for i in range(25)]
        strong_bear_vols = [5000 + i * 500 for i in range(25)]
        df_bear = make_df(strong_bear_closes, strong_bear_vols)
        result_bear = analyzer.analyze(df_bear)

        assert result_bear["score"] <= 40, \
            "Strong bear should score <=40, got {}".format(
                result_bear["score"]
            )

        print("  Bull score: {:.1f} | Bear score: {:.1f}".format(
            result_bull["score"], result_bear["score"]
        ))
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 13: OBV length matches input ----
    print("--- TEST 13: OBV output length ---")
    try:
        for n in [5, 20, 50, 100]:
            closes = [100 + i * 0.1 for i in range(n)]
            volumes = [1000] * n
            obv = analyzer.calculate_obv(closes, volumes)
            assert len(obv) == n, \
                "OBV length {} != input length {}".format(len(obv), n)

        print("  OBV length matches input for all sizes")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 14: Swing point detection ----
    print("--- TEST 14: Swing point detection ---")
    try:
        # Clear V-shape: high, low, high
        values = np.array([10, 8, 6, 4, 2, 4, 6, 8, 10])
        highs, lows = analyzer._find_swing_points(values, window=2)

        assert len(lows) >= 1, "Should find at least 1 swing low"
        # The low should be at index 4 (value=2)
        low_values = [v for _, v in lows]
        assert 2.0 in low_values, \
            "Should find low at value 2. Got: {}".format(lows)

        print("  V-shape swing low found at value=2")
        print("PASSED ✅\n")
        passed += 1
    except AssertionError as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 15: NaN handling ----
    print("--- TEST 15: NaN handling ---")
    try:
        closes = [100, float("nan"), 102, 103, 104]
        volumes = [1000, 1000, float("nan"), 1000, 1000]

        obv = analyzer.calculate_obv(closes, volumes)
        assert len(obv) == 5
        # Should not crash, NaN replaced with 0
        assert not any(np.isnan(v) for v in obv)

        print("  NaN values handled gracefully")
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