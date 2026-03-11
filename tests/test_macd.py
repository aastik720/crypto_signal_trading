# ============================================
# MACD ANALYZER TEST SCRIPT
# ============================================
# Run: python test_macd.py
#
# Tests all 8 MACD functions with synthetic
# price data covering every signal scenario.
# ============================================

import numpy as np
import pandas as pd


def make_df(close_prices):
    """Helper: creates a DataFrame from close prices list."""
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
    """Test all MACD functions."""

    from algorithms.macd import MACDAnalyzer

    analyzer = MACDAnalyzer(fast=12, slow=26, signal_period=9)

    print("\n" + "=" * 55)
    print("   RUNNING MACD ANALYZER TESTS")
    print("=" * 55 + "\n")

    # ---- TEST 1: EMA calculation ----
    print("--- TEST 1: calculate_ema ---")
    # Simple ascending prices
    prices = pd.Series([float(i + 100) for i in range(50)])
    ema_12 = analyzer.calculate_ema(prices, 12)

    assert ema_12 is not None, "EMA should not be None"
    assert len(ema_12) == 50, "EMA length should match input"

    # First 11 values should be NaN (period-1)
    nan_count = ema_12[:11].isna().sum()
    assert nan_count == 11, "First 11 should be NaN, got {} NaN".format(nan_count)

    # Value at index 11 should be SMA of first 12 values
    expected_sma = prices[:12].mean()
    actual = ema_12.iloc[11]
    assert abs(actual - expected_sma) < 0.01, (
        "First EMA should equal SMA: {:.2f} vs {:.2f}".format(
            actual, expected_sma
        ))

    # EMA should be less than latest price in uptrend
    # (EMA lags behind in trending market)
    assert ema_12.iloc[-1] < prices.iloc[-1], "EMA should lag in uptrend"

    print("  EMA(12) first: {:.2f} | last: {:.2f}".format(
        ema_12.dropna().iloc[0], ema_12.iloc[-1]
    ))
    print("PASSED ✅\n")

    # ---- TEST 2: EMA edge cases ----
    print("--- TEST 2: EMA edge cases ---")

    # Empty series
    result = analyzer.calculate_ema(pd.Series(dtype=float), 12)
    assert result is None, "Empty series should return None"

    # Too short
    result = analyzer.calculate_ema(pd.Series([1.0, 2.0, 3.0]), 12)
    assert result is None, "Too-short series should return None"

    # Invalid period
    result = analyzer.calculate_ema(prices, 0)
    assert result is None, "Period 0 should return None"

    print("  All edge cases handled correctly")
    print("PASSED ✅\n")

    # ---- TEST 3: MACD calculation ----
    print("--- TEST 3: calculate_macd ---")
    # 60 candles of uptrend (enough for 26+9 = 35 minimum)
    prices_up = [100.0 + i * 0.5 for i in range(60)]
    df_up = make_df(prices_up)
    macd_data = analyzer.calculate_macd(df_up)

    assert macd_data is not None, "MACD data should not be None"
    assert "macd_line" in macd_data
    assert "signal_line" in macd_data
    assert "histogram" in macd_data

    macd_line = macd_data["macd_line"]
    signal_line = macd_data["signal_line"]
    histogram = macd_data["histogram"]

    # In uptrend, MACD should be positive (fast > slow)
    valid_macd = macd_line.dropna()
    assert valid_macd.iloc[-1] > 0, (
        "MACD should be positive in uptrend, got {:.6f}".format(
            valid_macd.iloc[-1]
        ))

    print("  MACD: {:.6f} | Signal: {:.6f} | Hist: {:.6f}".format(
        valid_macd.iloc[-1],
        signal_line.dropna().iloc[-1],
        histogram.dropna().iloc[-1],
    ))
    print("PASSED ✅\n")

    # ---- TEST 4: MACD in downtrend ----
    print("--- TEST 4: MACD in downtrend ---")
    prices_down = [150.0 - i * 0.5 for i in range(60)]
    df_down = make_df(prices_down)
    macd_down = analyzer.calculate_macd(df_down)

    assert macd_down is not None
    last_macd = macd_down["macd_line"].dropna().iloc[-1]
    assert last_macd < 0, (
        "MACD should be negative in downtrend, got {:.6f}".format(last_macd)
    )
    print("  MACD in downtrend: {:.6f} (correctly negative)".format(last_macd))
    print("PASSED ✅\n")

    # ---- TEST 5: Crossover detection ----
    print("--- TEST 5: detect_crossover ---")

    # Simulate bullish cross: MACD below signal, then above
    macd_series = pd.Series([-1.0, -0.5, 0.5, 1.0])
    signal_series = pd.Series([0.0, 0.0, 0.0, 0.0])
    result = analyzer.detect_crossover(macd_series, signal_series)
    assert result == "BULLISH_CROSS", "Should be BULLISH_CROSS, got {}".format(result)

    # Simulate bearish cross: MACD above signal, then below
    macd_bear = pd.Series([1.0, 0.5, -0.5, -1.0])
    result = analyzer.detect_crossover(macd_bear, signal_series)
    assert result == "BEARISH_CROSS", "Should be BEARISH_CROSS, got {}".format(result)

    # No cross
    macd_no = pd.Series([1.0, 2.0, 3.0, 4.0])
    result = analyzer.detect_crossover(macd_no, signal_series)
    assert result == "NONE", "Should be NONE, got {}".format(result)

    # None input
    assert analyzer.detect_crossover(None, None) == "NONE"

    print("  All crossover checks passed")
    print("PASSED ✅\n")

    # ---- TEST 6: Zero line cross ----
    print("--- TEST 6: detect_zero_cross ---")

    # Bullish zero cross
    macd_zero_bull = pd.Series([-2.0, -0.5, 0.5])
    result = analyzer.detect_zero_cross(macd_zero_bull)
    assert result == "BULLISH_ZERO_CROSS"

    # Bearish zero cross
    macd_zero_bear = pd.Series([2.0, 0.5, -0.5])
    result = analyzer.detect_zero_cross(macd_zero_bear)
    assert result == "BEARISH_ZERO_CROSS"

    # No cross
    macd_no_cross = pd.Series([1.0, 2.0, 3.0])
    result = analyzer.detect_zero_cross(macd_no_cross)
    assert result == "NONE"

    # None input
    assert analyzer.detect_zero_cross(None) == "NONE"

    print("  All zero-line cross checks passed")
    print("PASSED ✅\n")

    # ---- TEST 7: Histogram analysis ----
    print("--- TEST 7: analyze_histogram ---")

    # Growing positive histogram
    hist_growing = pd.Series([0.1, 0.3, 0.5, 0.8, 1.2])
    result = analyzer.analyze_histogram(hist_growing)
    assert result["direction"] == "GROWING"
    assert result["flip"] is False

    # Shrinking histogram
    hist_shrinking = pd.Series([1.2, 0.8, 0.5, 0.3, 0.1])
    result = analyzer.analyze_histogram(hist_shrinking)
    assert result["direction"] == "SHRINKING"

    # Flip from negative to positive
    hist_flip = pd.Series([-0.5, -0.2, 0.1, 0.3, 0.5])
    result = analyzer.analyze_histogram(hist_flip)
    assert result["flip"] is True, "Should detect flip"

    # None input
    result = analyzer.analyze_histogram(None)
    assert result["direction"] == "FLAT"
    assert result["momentum"] == "NEUTRAL"
    assert result["flip"] is False

    print("  All histogram checks passed")
    print("PASSED ✅\n")

    # ---- TEST 8: Divergence detection ----
    print("--- TEST 8: detect_divergence ---")

    # We test that the function doesn't crash and returns
    # correct structure even with difficult data
    prices_div = [100 + i * 0.3 for i in range(60)]
    df_div = make_df(prices_div)
    macd_div_data = analyzer.calculate_macd(df_div)

    if macd_div_data is not None:
        div_result = analyzer.detect_divergence(
            df_div, macd_div_data["macd_line"], lookback=20
        )
        assert isinstance(div_result, dict)
        assert "bullish_divergence" in div_result
        assert "bearish_divergence" in div_result
    else:
        print("  Skipped (MACD calc returned None for test data)")

    # Edge: None inputs
    div_none = analyzer.detect_divergence(None, None)
    assert div_none["bullish_divergence"] is False
    assert div_none["bearish_divergence"] is False

    print("  Divergence structure and edge cases verified")
    print("PASSED ✅\n")

    # ---- TEST 9: Full analyze() — Uptrend ----
    print("--- TEST 9: analyze() on uptrend (60 candles) ---")
    prices_trend = [100.0 + i * 0.5 for i in range(60)]
    df_trend = make_df(prices_trend)
    result = analyzer.analyze(df_trend)

    assert result is not None
    assert result["brain"] == "MACD"
    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert 0 <= result["confidence"] <= 100
    assert "macd_value" in result
    assert "signal_value" in result
    assert "histogram_value" in result
    assert "crossover" in result["details"]
    assert "zero_cross" in result["details"]
    assert "histogram" in result["details"]
    assert "divergence" in result["details"]

    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  MACD       : {:.6f}".format(result["macd_value"]))
    print("  Signal     : {:.6f}".format(result["signal_value"]))
    print("  Histogram  : {:.6f}".format(result["histogram_value"]))
    print("PASSED ✅\n")

    # ---- TEST 10: Full analyze() — Downtrend ----
    print("--- TEST 10: analyze() on downtrend ---")
    prices_bear = [150.0 - i * 0.5 for i in range(60)]
    df_bear = make_df(prices_bear)
    result = analyzer.analyze(df_bear)

    assert result["brain"] == "MACD"
    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("PASSED ✅\n")

    # ---- TEST 11: Full analyze() — Choppy market ----
    print("--- TEST 11: analyze() on choppy market ---")
    np.random.seed(42)
    prices_choppy = [100.0 + np.sin(i * 0.5) * 2 + np.random.randn() * 0.5
                     for i in range(60)]
    df_choppy = make_df(prices_choppy)
    result = analyzer.analyze(df_choppy)

    assert result["brain"] == "MACD"
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("PASSED ✅\n")

    # ---- TEST 12: Edge — Insufficient data ----
    print("--- TEST 12: Insufficient data (20 candles) ---")
    tiny = make_df([100.0 + i for i in range(20)])
    result = analyzer.analyze(tiny)
    assert result["direction"] == "NEUTRAL"
    assert result["confidence"] == 0
    print("  Correctly returned NEUTRAL for too little data")
    print("PASSED ✅\n")

    # ---- TEST 13: Edge — Empty and None ----
    print("--- TEST 13: Empty/None DataFrame ---")
    result = analyzer.analyze(pd.DataFrame())
    assert result["direction"] == "NEUTRAL"

    result = analyzer.analyze(None)
    assert result["direction"] == "NEUTRAL"

    print("  Correctly handled empty/None")
    print("PASSED ✅\n")

    # ---- TEST 14: Result structure completeness ----
    print("--- TEST 14: Result structure validation ---")
    result = analyzer.analyze(df_trend)

    required_keys = ["brain", "direction", "confidence",
                     "macd_value", "signal_value", "histogram_value",
                     "details"]
    for key in required_keys:
        assert key in result, "Missing key: {}".format(key)

    detail_keys = ["crossover", "zero_cross", "histogram", "divergence"]
    for key in detail_keys:
        assert key in result["details"], "Missing detail key: {}".format(key)

    hist_keys = ["direction", "momentum", "flip"]
    for key in hist_keys:
        assert key in result["details"]["histogram"], (
            "Missing histogram key: {}".format(key)
        )

    print("  All {} keys present".format(
        len(required_keys) + len(detail_keys) + len(hist_keys)
    ))
    print("PASSED ✅\n")

    # ---- FINAL SUMMARY ----
    print("=" * 55)
    print("   ALL 14 TESTS PASSED ✅✅✅")
    print("=" * 55)


if __name__ == "__main__":
    run_tests()