# ============================================
# BOLLINGER BANDS ANALYZER TEST SCRIPT
# ============================================
# Run: python test_bollinger.py
# ============================================

import numpy as np
import pandas as pd


def make_df(close_prices, high_offset=1.002, low_offset=0.998,
            base_volume=1000.0):
    """Helper: creates a DataFrame from close prices list."""
    n = len(close_prices)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
        "open":   [float(p) * 0.999 for p in close_prices],
        "high":   [float(p) * high_offset for p in close_prices],
        "low":    [float(p) * low_offset for p in close_prices],
        "close":  [float(p) for p in close_prices],
        "volume": [base_volume + i * 10 for i in range(n)],
    })


def run_tests():
    """Test all Bollinger functions."""

    from algorithms.bollinger import BollingerAnalyzer

    analyzer = BollingerAnalyzer(period=20, std_dev=2)

    print("\n" + "=" * 55)
    print("   RUNNING BOLLINGER ANALYZER TESTS")
    print("=" * 55 + "\n")

    # ---- TEST 1: Band calculation — Uptrend ----
    print("--- TEST 1: calculate_bands (uptrend) ---")
    prices_up = [100.0 + i * 0.5 for i in range(50)]
    df_up = make_df(prices_up)
    bands = analyzer.calculate_bands(df_up)

    assert bands is not None, "Bands should not be None"
    assert "upper" in bands
    assert "middle" in bands
    assert "lower" in bands

    upper = bands["upper"]
    middle = bands["middle"]
    lower = bands["lower"]

    # First 19 values should be NaN
    nan_count = middle[:19].isna().sum()
    assert nan_count == 19, "First 19 should be NaN, got {}".format(nan_count)

    # Upper > Middle > Lower always
    valid_idx = middle.dropna().index
    for idx in valid_idx:
        assert upper.loc[idx] > middle.loc[idx] > lower.loc[idx], (
            "Upper > Middle > Lower violated at {}".format(idx)
        )

    print("  Upper: {:.4f} | Mid: {:.4f} | Lower: {:.4f}".format(
        upper.dropna().iloc[-1],
        middle.dropna().iloc[-1],
        lower.dropna().iloc[-1],
    ))
    print("PASSED ✅\n")

    # ---- TEST 2: Band calculation — Flat market ----
    print("--- TEST 2: calculate_bands (flat market) ---")
    prices_flat = [100.0] * 50
    df_flat = make_df(prices_flat)
    bands_flat = analyzer.calculate_bands(df_flat)

    assert bands_flat is not None
    # Flat market → std dev = 0 → upper = middle = lower
    last_upper = bands_flat["upper"].dropna().iloc[-1]
    last_middle = bands_flat["middle"].dropna().iloc[-1]
    last_lower = bands_flat["lower"].dropna().iloc[-1]
    assert last_upper == last_middle == last_lower == 100.0, (
        "Flat market: all bands should equal 100"
    )
    print("  Flat market: all bands = {:.4f}".format(last_middle))
    print("PASSED ✅\n")

    # ---- TEST 3: Band edge cases ----
    print("--- TEST 3: Band edge cases ---")
    assert analyzer.calculate_bands(None) is None
    assert analyzer.calculate_bands(pd.DataFrame()) is None

    too_short = make_df([100.0] * 10)
    assert analyzer.calculate_bands(too_short) is None

    no_close = pd.DataFrame({"open": [100.0] * 30})
    assert analyzer.calculate_bands(no_close) is None

    print("  All edge cases handled correctly")
    print("PASSED ✅\n")

    # ---- TEST 4: %B calculation ----
    print("--- TEST 4: calculate_percent_b ---")
    close = pd.Series([100.0, 105.0, 95.0, 110.0, 90.0])
    upper_test = pd.Series([110.0, 110.0, 110.0, 110.0, 110.0])
    lower_test = pd.Series([90.0, 90.0, 90.0, 90.0, 90.0])

    pb = analyzer.calculate_percent_b(close, upper_test, lower_test)

    assert pb is not None
    # close=100: (100-90)/(110-90) = 10/20 = 0.5
    assert abs(pb.iloc[0] - 0.5) < 0.001, "Got {}".format(pb.iloc[0])
    # close=110: (110-90)/(110-90) = 20/20 = 1.0
    assert abs(pb.iloc[3] - 1.0) < 0.001
    # close=90: (90-90)/(110-90) = 0/20 = 0.0
    assert abs(pb.iloc[4] - 0.0) < 0.001

    # None inputs
    assert analyzer.calculate_percent_b(None, None, None) is None

    print("  %B at middle: {:.4f}".format(pb.iloc[0]))
    print("  %B at upper:  {:.4f}".format(pb.iloc[3]))
    print("  %B at lower:  {:.4f}".format(pb.iloc[4]))
    print("PASSED ✅\n")

    # ---- TEST 5: Bandwidth calculation ----
    print("--- TEST 5: calculate_bandwidth ---")
    bw = analyzer.calculate_bandwidth(upper_test, lower_test,
                                      pd.Series([100.0] * 5))
    assert bw is not None
    # (110-90)/100 * 100 = 20%
    assert abs(bw.iloc[0] - 20.0) < 0.001
    print("  Bandwidth: {:.2f}%".format(bw.iloc[0]))

    # None inputs
    assert analyzer.calculate_bandwidth(None, None, None) is None

    print("PASSED ✅\n")

    # ---- TEST 6: Squeeze detection ----
    print("--- TEST 6: detect_squeeze ---")
    # Create bandwidth that narrows (squeeze at end)
    bw_squeeze = pd.Series([20.0, 18.0, 16.0, 14.0, 12.0,
                            10.0, 8.0, 6.0, 4.0, 3.0])
    result = analyzer.detect_squeeze(bw_squeeze, lookback=10)
    assert result["is_squeeze"] is True, (
        "Should detect squeeze, got {}".format(result)
    )
    assert result["squeeze_strength"] > 0

    # No squeeze: bandwidth at maximum
    bw_wide = pd.Series([3.0, 5.0, 8.0, 12.0, 16.0,
                         18.0, 20.0, 22.0, 24.0, 25.0])
    result = analyzer.detect_squeeze(bw_wide, lookback=10)
    assert result["is_squeeze"] is False

    # None input
    result = analyzer.detect_squeeze(None)
    assert result["is_squeeze"] is False

    print("  Squeeze detection working correctly")
    print("PASSED ✅\n")

    # ---- TEST 7: Bounce detection ----
    print("--- TEST 7: detect_bounce ---")
    # Simulate bounce from lower band:
    # Price drops to touch lower band, then recovers
    bounce_prices = [100, 98, 96, 94, 97]
    df_bounce = make_df(bounce_prices)

    # Set bands where lower band = 94.5 (price touched at 94)
    upper_b = pd.Series([110.0] * 5, index=df_bounce.index)
    lower_b = pd.Series([94.5] * 5, index=df_bounce.index)

    result = analyzer.detect_bounce(df_bounce, upper_b, lower_b)
    assert result == "BOUNCE_LOWER", "Expected BOUNCE_LOWER, got {}".format(result)

    # Simulate bounce from upper band
    bounce_up = [100, 102, 104, 106, 103]
    df_bounce_up = make_df(bounce_up)
    upper_b2 = pd.Series([105.5] * 5, index=df_bounce_up.index)
    lower_b2 = pd.Series([90.0] * 5, index=df_bounce_up.index)

    result = analyzer.detect_bounce(df_bounce_up, upper_b2, lower_b2)
    assert result == "BOUNCE_UPPER", "Expected BOUNCE_UPPER, got {}".format(result)

    # None input
    assert analyzer.detect_bounce(None, None, None) == "NONE"

    print("  Bounce detection working correctly")
    print("PASSED ✅\n")

    # ---- TEST 8: Breakout detection ----
    print("--- TEST 8: detect_breakout ---")
    # Breakout up: close above upper band with momentum
    breakout_prices = [100, 102, 105, 108, 112]
    df_break = make_df(breakout_prices, base_volume=2000)
    upper_br = pd.Series([110.0] * 5, index=df_break.index)
    lower_br = pd.Series([90.0] * 5, index=df_break.index)

    result = analyzer.detect_breakout(df_break, upper_br, lower_br)
    assert result == "BREAKOUT_UP", "Expected BREAKOUT_UP, got {}".format(result)

    # Breakout down: close below lower band
    break_down_prices = [100, 98, 95, 92, 88]
    df_break_down = make_df(break_down_prices, base_volume=2000)
    upper_bd = pd.Series([110.0] * 5, index=df_break_down.index)
    lower_bd = pd.Series([90.0] * 5, index=df_break_down.index)

    result = analyzer.detect_breakout(df_break_down, upper_bd, lower_bd)
    assert result == "BREAKOUT_DOWN", (
        "Expected BREAKOUT_DOWN, got {}".format(result)
    )

    # None input
    assert analyzer.detect_breakout(None, None, None) == "NONE"

    print("  Breakout detection working correctly")
    print("PASSED ✅\n")

    # ---- TEST 9: Band walk detection ----
    print("--- TEST 9: detect_band_walk ---")
    # Walking upper: all highs near upper band
    walk_prices = [108, 109, 110, 109.5, 110.5]
    df_walk = make_df(walk_prices, high_offset=1.001, low_offset=0.999)
    upper_w = pd.Series([110.5] * 5, index=df_walk.index)
    lower_w = pd.Series([90.0] * 5, index=df_walk.index)

    result = analyzer.detect_band_walk(df_walk, upper_w, lower_w, periods=5)
    # Highs are at price*1.001 ≈ 108.1, 109.1, 110.1, 109.6, 110.6
    # Upper band = 110.5
    # Some of these should be within 0.3%
    print("  Band walk result: {}".format(result))

    # None input
    assert analyzer.detect_band_walk(None, None, None) == "NONE"

    print("PASSED ✅\n")

    # ---- TEST 10: Full analyze() — Normal market ----
    print("--- TEST 10: analyze() on normal market ---")
    prices_normal = [100.0 + np.sin(i * 0.3) * 3 for i in range(50)]
    df_normal = make_df(prices_normal)
    result = analyzer.analyze(df_normal)

    assert result is not None
    assert result["brain"] == "BOLLINGER"
    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert 0 <= result["confidence"] <= 100
    assert result["upper_band"] > 0
    assert result["middle_band"] > 0
    assert result["lower_band"] > 0
    assert "percent_b" in result
    assert "bandwidth" in result
    assert "squeeze" in result["details"]
    assert "bounce" in result["details"]
    assert "breakout" in result["details"]
    assert "band_walk" in result["details"]

    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  Upper      : {:.4f}".format(result["upper_band"]))
    print("  Middle     : {:.4f}".format(result["middle_band"]))
    print("  Lower      : {:.4f}".format(result["lower_band"]))
    print("  %B         : {:.4f}".format(result["percent_b"]))
    print("PASSED ✅\n")

    # ---- TEST 11: Full analyze() — Strong uptrend ----
    print("--- TEST 11: analyze() on strong uptrend ---")
    prices_bull = [100.0 + i * 1.0 for i in range(50)]
    df_bull = make_df(prices_bull)
    result = analyzer.analyze(df_bull)

    assert result["brain"] == "BOLLINGER"
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  %B         : {:.4f}".format(result["percent_b"]))
    print("PASSED ✅\n")

    # ---- TEST 12: Full analyze() — Strong downtrend ----
    print("--- TEST 12: analyze() on strong downtrend ---")
    prices_bear = [150.0 - i * 1.0 for i in range(50)]
    df_bear = make_df(prices_bear)
    result = analyzer.analyze(df_bear)

    assert result["brain"] == "BOLLINGER"
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  %B         : {:.4f}".format(result["percent_b"]))
    print("PASSED ✅\n")

    # ---- TEST 13: Edge — Insufficient data ----
    print("--- TEST 13: Insufficient data (15 candles) ---")
    tiny = make_df([100.0 + i for i in range(15)])
    result = analyzer.analyze(tiny)
    assert result["direction"] == "NEUTRAL"
    assert result["confidence"] == 0
    print("  Correctly returned NEUTRAL for too little data")
    print("PASSED ✅\n")

    # ---- TEST 14: Edge — Empty and None ----
    print("--- TEST 14: Empty/None DataFrame ---")
    result = analyzer.analyze(pd.DataFrame())
    assert result["direction"] == "NEUTRAL"

    result = analyzer.analyze(None)
    assert result["direction"] == "NEUTRAL"

    print("  Correctly handled empty/None")
    print("PASSED ✅\n")

    # ---- TEST 15: Result structure completeness ----
    print("--- TEST 15: Result structure validation ---")
    result = analyzer.analyze(df_normal)

    required_keys = [
        "brain", "direction", "confidence",
        "upper_band", "middle_band", "lower_band",
        "percent_b", "bandwidth", "details"
    ]
    for key in required_keys:
        assert key in result, "Missing key: {}".format(key)

    detail_keys = ["squeeze", "bounce", "breakout", "band_walk"]
    for key in detail_keys:
        assert key in result["details"], (
            "Missing detail key: {}".format(key)
        )

    print("  All {} keys present".format(
        len(required_keys) + len(detail_keys)
    ))
    print("PASSED ✅\n")

    # ---- FINAL SUMMARY ----
    print("=" * 55)
    print("   ALL 15 TESTS PASSED ✅✅✅")
    print("=" * 55)


if __name__ == "__main__":
    run_tests()