# ============================================
# EMA CROSSOVER ANALYZER TEST SCRIPT
# ============================================
# Run: python test_ema_crossover.py
# ============================================

import numpy as np
import pandas as pd


def make_df(close_prices):
    """Helper: creates DataFrame from close prices."""
    n = len(close_prices)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
        "open":   [float(p) * 0.999 for p in close_prices],
        "high":   [float(p) * 1.002 for p in close_prices],
        "low":    [float(p) * 0.998 for p in close_prices],
        "close":  [float(p) for p in close_prices],
        "volume": [1000.0 + i * 10 for i in range(n)],
    })


def run_tests():
    """Test all EMA Crossover functions."""

    from algorithms.ema_crossover import EMACrossoverAnalyzer

    analyzer = EMACrossoverAnalyzer()

    print("\n" + "=" * 55)
    print("   RUNNING EMA CROSSOVER TESTS")
    print("=" * 55 + "\n")

    # ---- TEST 1: Single EMA calculation ----
    print("--- TEST 1: calculate_ema ---")
    prices = pd.Series([float(100 + i * 0.5) for i in range(60)])
    ema_9 = analyzer.calculate_ema(prices, 9)

    assert ema_9 is not None, "EMA should not be None"
    assert len(ema_9) == 60
    nan_count = ema_9[:8].isna().sum()
    assert nan_count == 8, "First 8 should be NaN, got {}".format(nan_count)

    # First EMA = SMA of first 9 values
    expected_sma = prices[:9].mean()
    assert abs(ema_9.iloc[8] - expected_sma) < 0.01

    # EMA should lag in uptrend
    assert ema_9.iloc[-1] < prices.iloc[-1]

    print("  EMA(9) first: {:.2f} | last: {:.2f}".format(
        ema_9.dropna().iloc[0], ema_9.iloc[-1]
    ))
    print("PASSED ✅\n")

    # ---- TEST 2: EMA edge cases ----
    print("--- TEST 2: EMA edge cases ---")
    assert analyzer.calculate_ema(None, 9) is None
    assert analyzer.calculate_ema(pd.Series(dtype=float), 9) is None
    assert analyzer.calculate_ema(prices, 0) is None
    assert analyzer.calculate_ema(pd.Series([1.0, 2.0]), 9) is None
    print("  All edge cases handled")
    print("PASSED ✅\n")

    # ---- TEST 3: Calculate all EMAs — 60 candles ----
    print("--- TEST 3: calculate_all_emas (60 candles) ---")
    prices_60 = [100.0 + i * 0.5 for i in range(60)]
    df_60 = make_df(prices_60)
    emas = analyzer.calculate_all_emas(df_60)

    assert emas is not None
    assert 9 in emas["available_periods"]
    assert 21 in emas["available_periods"]
    assert 50 in emas["available_periods"]
    # 100 and 200 should NOT be available (only 60 candles)
    assert 100 not in emas["available_periods"]
    assert 200 not in emas["available_periods"]
    assert emas["ema_100"] is None
    assert emas["ema_200"] is None

    print("  Available EMAs: {}".format(emas["available_periods"]))
    print("PASSED ✅\n")

    # ---- TEST 4: Calculate all EMAs — 250 candles ----
    print("--- TEST 4: calculate_all_emas (250 candles) ---")
    prices_250 = [100.0 + i * 0.2 for i in range(250)]
    df_250 = make_df(prices_250)
    emas_250 = analyzer.calculate_all_emas(df_250)

    assert emas_250 is not None
    assert len(emas_250["available_periods"]) == 5
    for p in [9, 21, 50, 100, 200]:
        assert p in emas_250["available_periods"]

    print("  All 5 EMAs available: {}".format(
        emas_250["available_periods"]
    ))
    print("PASSED ✅\n")

    # ---- TEST 5: EMA alignment — uptrend ----
    print("--- TEST 5: check_ema_alignment (uptrend) ---")
    # Strong uptrend: EMA9 > EMA21 > EMA50 (all available)
    align = analyzer.check_ema_alignment(emas)
    assert align is not None
    assert "alignment" in align
    assert align["bullish_count"] >= 0
    assert align["bearish_count"] >= 0

    # With 250 candle uptrend, should be bullish
    align_250 = analyzer.check_ema_alignment(emas_250)
    assert "BULLISH" in align_250["alignment"], (
        "Uptrend should be bullish, got {}".format(
            align_250["alignment"]
        ))

    print("  60-candle alignment: {}".format(align["alignment"]))
    print("  250-candle alignment: {}".format(align_250["alignment"]))
    print("PASSED ✅\n")

    # ---- TEST 6: EMA alignment — downtrend ----
    print("--- TEST 6: check_ema_alignment (downtrend) ---")
    prices_down = [200.0 - i * 0.2 for i in range(250)]
    df_down = make_df(prices_down)
    emas_down = analyzer.calculate_all_emas(df_down)
    align_down = analyzer.check_ema_alignment(emas_down)

    assert "BEARISH" in align_down["alignment"], (
        "Downtrend should be bearish, got {}".format(
            align_down["alignment"]
        ))

    print("  Downtrend alignment: {}".format(align_down["alignment"]))
    print("PASSED ✅\n")

    # ---- TEST 7: Crossover detection ----
    print("--- TEST 7: detect_crossovers ---")
    # Create data where EMA9 crosses above EMA21
    # Start flat then trend up → causes cross
    cross_prices = [100.0] * 30 + [100.0 + i * 1.5 for i in range(30)]
    df_cross = make_df(cross_prices)
    emas_cross = analyzer.calculate_all_emas(df_cross)
    cross_result = analyzer.detect_crossovers(emas_cross, lookback=5)

    assert cross_result is not None
    assert "crossovers" in cross_result
    assert "golden_cross" in cross_result
    assert "death_cross" in cross_result
    assert "most_recent" in cross_result

    print("  Crossovers found: {}".format(len(cross_result["crossovers"])))
    print("  Golden cross: {}".format(cross_result["golden_cross"]))
    print("  Death cross: {}".format(cross_result["death_cross"]))
    print("  Most recent: {}".format(cross_result["most_recent"]))

    # None input
    assert analyzer.detect_crossovers(None)["most_recent"] == "NONE"
    print("PASSED ✅\n")

    # ---- TEST 8: Price position ----
    print("--- TEST 8: check_price_position ---")
    pos = analyzer.check_price_position(df_250, emas_250)

    assert pos is not None
    assert "position" in pos
    assert "above_count" in pos
    assert "below_count" in pos

    # In uptrend, price should be above most/all EMAs
    print("  Position: {} | Above: {} | Below: {}".format(
        pos["position"], pos["above_count"], pos["below_count"]
    ))

    # None input
    assert analyzer.check_price_position(None, None)["position"] == "MIXED"
    print("PASSED ✅\n")

    # ---- TEST 9: EMA slopes ----
    print("--- TEST 9: calculate_ema_slopes ---")
    slopes = analyzer.calculate_ema_slopes(emas_250, lookback=5)

    assert slopes is not None
    assert "all_rising" in slopes
    assert "all_falling" in slopes
    assert "overall_slope" in slopes

    # Uptrend should have rising slopes
    print("  Overall slope: {}".format(slopes["overall_slope"]))
    print("  All rising: {}".format(slopes["all_rising"]))
    print("  EMA9 slope: {}".format(slopes["ema_9_slope"]))
    print("  EMA50 slope: {}".format(slopes["ema_50_slope"]))

    # None input
    assert analyzer.calculate_ema_slopes(None)["overall_slope"] == "NEUTRAL"
    print("PASSED ✅\n")

    # ---- TEST 10: EMA distance ----
    print("--- TEST 10: calculate_ema_distance ---")
    dist = analyzer.calculate_ema_distance(emas_250)

    assert dist is not None
    assert "spread_condition" in dist
    assert "overextended" in dist
    assert "ema_9_21_distance" in dist

    print("  Spread: {}".format(dist["spread_condition"]))
    print("  Overextended: {}".format(dist["overextended"]))
    print("  EMA 9/21 dist: {:.4f}%".format(dist["ema_9_21_distance"]))

    # None input
    assert analyzer.calculate_ema_distance(None)["spread_condition"] == "NORMAL"
    print("PASSED ✅\n")

    # ---- TEST 11: EMA bounce ----
    print("--- TEST 11: detect_ema_bounce ---")
    # Create bounce scenario: price dips to EMA21 and recovers
    bounce_prices = [100 + i * 0.3 for i in range(50)]
    # Dip the last few candles then recover
    bounce_prices[-5] = bounce_prices[-6] - 1.0  # dip
    bounce_prices[-4] = bounce_prices[-5] - 0.5  # dip more
    bounce_prices[-3] = bounce_prices[-4] + 0.3  # start recovery
    bounce_prices[-2] = bounce_prices[-3] + 0.8  # recover
    bounce_prices[-1] = bounce_prices[-2] + 0.5  # recover more

    df_bounce = make_df(bounce_prices)
    emas_bounce = analyzer.calculate_all_emas(df_bounce)
    bounce_result = analyzer.detect_ema_bounce(df_bounce, emas_bounce)

    assert bounce_result is not None
    assert "bounce_detected" in bounce_result
    assert "bounced_from" in bounce_result
    assert "bounce_direction" in bounce_result
    assert "bounce_strength" in bounce_result

    print("  Bounce: {} | From: {} | Dir: {}".format(
        bounce_result["bounce_detected"],
        bounce_result["bounced_from"],
        bounce_result["bounce_direction"]
    ))

    # None input
    assert analyzer.detect_ema_bounce(None, None)["bounce_detected"] is False
    print("PASSED ✅\n")

    # ---- TEST 12: Full analyze() — Uptrend (250 candles) ----
    print("--- TEST 12: analyze() uptrend (250 candles) ---")
    result = analyzer.analyze(df_250)

    assert result is not None
    assert result["brain"] == "EMA_CROSSOVER"
    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert 0 <= result["confidence"] <= 100
    assert result["current_price"] > 0
    assert "ema_values" in result
    assert "details" in result
    assert "alignment" in result["details"]
    assert "crossovers" in result["details"]
    assert "price_position" in result["details"]
    assert "slopes" in result["details"]
    assert "ema_distance" in result["details"]
    assert "bounce" in result["details"]
    assert "trend_strength" in result["details"]

    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  Trend      : {}".format(
        result["details"]["trend_strength"]
    ))
    print("PASSED ✅\n")

    # ---- TEST 13: Full analyze() — Downtrend ----
    print("--- TEST 13: analyze() downtrend ---")
    result_down = analyzer.analyze(df_down)
    assert result_down["brain"] == "EMA_CROSSOVER"
    print("  Direction  : {}".format(result_down["direction"]))
    print("  Confidence : {:.1f}%".format(result_down["confidence"]))
    print("PASSED ✅\n")

    # ---- TEST 14: Full analyze() — Choppy/Sideways ----
    print("--- TEST 14: analyze() choppy market ---")
    np.random.seed(42)
    choppy = [100.0 + np.sin(i * 0.5) * 3 + np.random.randn() * 0.5
              for i in range(80)]
    df_choppy = make_df(choppy)
    result_choppy = analyzer.analyze(df_choppy)
    assert result_choppy["brain"] == "EMA_CROSSOVER"
    print("  Direction  : {}".format(result_choppy["direction"]))
    print("  Confidence : {:.1f}%".format(result_choppy["confidence"]))
    print("PASSED ✅\n")

    # ---- TEST 15: Edge — 60 candles (no EMA100/200) ----
    print("--- TEST 15: Limited data (60 candles) ---")
    result_60 = analyzer.analyze(df_60)
    assert result_60["brain"] == "EMA_CROSSOVER"
    assert result_60["ema_values"]["ema_100"] is None
    assert result_60["ema_values"]["ema_200"] is None
    print("  Works with 60 candles (no EMA100/200)")
    print("  Direction: {} | Confidence: {:.1f}%".format(
        result_60["direction"], result_60["confidence"]
    ))
    print("PASSED ✅\n")

    # ---- TEST 16: Edge — Insufficient data ----
    print("--- TEST 16: Insufficient data (30 candles) ---")
    tiny = make_df([100.0 + i for i in range(30)])
    result_tiny = analyzer.analyze(tiny)
    assert result_tiny["direction"] == "NEUTRAL"
    assert result_tiny["confidence"] == 0
    print("  Correctly returned NEUTRAL")
    print("PASSED ✅\n")

    # ---- TEST 17: Edge — Empty/None ----
    print("--- TEST 17: Empty/None DataFrame ---")
    assert analyzer.analyze(pd.DataFrame())["direction"] == "NEUTRAL"
    assert analyzer.analyze(None)["direction"] == "NEUTRAL"
    print("  Correctly handled empty/None")
    print("PASSED ✅\n")

    # ---- TEST 18: Result structure completeness ----
    print("--- TEST 18: Result structure validation ---")
    r = analyzer.analyze(df_250)

    top_keys = ["brain", "direction", "confidence",
                "current_price", "ema_values", "details"]
    for k in top_keys:
        assert k in r, "Missing: {}".format(k)

    ema_keys = ["ema_9", "ema_21", "ema_50", "ema_100", "ema_200"]
    for k in ema_keys:
        assert k in r["ema_values"], "Missing EMA: {}".format(k)

    detail_keys = ["alignment", "crossovers", "price_position",
                   "slopes", "ema_distance", "bounce",
                   "trend_strength"]
    for k in detail_keys:
        assert k in r["details"], "Missing detail: {}".format(k)

    total_keys = len(top_keys) + len(ema_keys) + len(detail_keys)
    print("  All {} keys verified".format(total_keys))
    print("PASSED ✅\n")

    # ---- FINAL SUMMARY ----
    print("=" * 55)
    print("   ALL 18 TESTS PASSED ✅✅✅")
    print("=" * 55)


if __name__ == "__main__":
    run_tests()