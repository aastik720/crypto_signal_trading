# ============================================
# VOLUME ANALYZER TEST SCRIPT
# ============================================
# Run: python test_volume.py
# ============================================

import numpy as np
import pandas as pd


def make_df(close_prices, volumes=None, high_offset=1.002,
            low_offset=0.998):
    """Helper: creates DataFrame from prices and optional volumes."""
    n = len(close_prices)
    if volumes is None:
        volumes = [1000.0 + i * 10 for i in range(n)]
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
        "open":   [float(p) * 0.999 for p in close_prices],
        "high":   [float(p) * high_offset for p in close_prices],
        "low":    [float(p) * low_offset for p in close_prices],
        "close":  [float(p) for p in close_prices],
        "volume": [float(v) for v in volumes],
    })


def run_tests():
    """Test all Volume functions."""

    from algorithms.volume import VolumeAnalyzer

    analyzer = VolumeAnalyzer(ma_period=20)

    print("\n" + "=" * 55)
    print("   RUNNING VOLUME ANALYZER TESTS")
    print("=" * 55 + "\n")

    # ---- TEST 1: Volume MA ----
    print("--- TEST 1: calculate_volume_ma ---")
    volumes = pd.Series([float(1000 + i * 10) for i in range(30)])
    vol_ma = analyzer.calculate_volume_ma(volumes)

    assert vol_ma is not None, "Volume MA should not be None"
    assert len(vol_ma) == 30, "Length should match"

    # First 19 values should be NaN
    nan_count = vol_ma[:19].isna().sum()
    assert nan_count == 19, "First 19 should be NaN, got {}".format(nan_count)

    # Value at index 19 should be SMA of first 20 volumes
    expected = volumes[:20].mean()
    actual = vol_ma.iloc[19]
    assert abs(actual - expected) < 0.01, (
        "First MA: {:.2f} vs expected {:.2f}".format(actual, expected)
    )
    print("  Vol MA working | First: {:.2f} | Last: {:.2f}".format(
        vol_ma.dropna().iloc[0], vol_ma.iloc[-1]
    ))
    print("PASSED ✅\n")

    # ---- TEST 2: Volume MA edge cases ----
    print("--- TEST 2: Volume MA edge cases ---")
    assert analyzer.calculate_volume_ma(None) is None
    assert analyzer.calculate_volume_ma(pd.Series(dtype=float)) is None

    too_short = pd.Series([100.0] * 10)
    assert analyzer.calculate_volume_ma(too_short) is None

    print("  All edge cases handled")
    print("PASSED ✅\n")

    # ---- TEST 3: Volume ratio ----
    print("--- TEST 3: calculate_volume_ratio ---")
    assert analyzer.calculate_volume_ratio(2000, 1000) == 2.0
    assert analyzer.calculate_volume_ratio(500, 1000) == 0.5
    assert analyzer.calculate_volume_ratio(1000, 1000) == 1.0
    assert analyzer.calculate_volume_ratio(0, 1000) == 0.0
    assert analyzer.calculate_volume_ratio(1000, 0) == 0.0
    assert analyzer.calculate_volume_ratio(None, None) == 0.0

    print("  All ratio calculations correct")
    print("PASSED ✅\n")

    # ---- TEST 4: OBV calculation ----
    print("--- TEST 4: calculate_obv ---")
    # Rising prices → OBV should increase
    prices_up = [100.0 + i * 0.5 for i in range(30)]
    vols_const = [1000.0] * 30
    df_up = make_df(prices_up, vols_const)
    obv = analyzer.calculate_obv(df_up)

    assert obv is not None, "OBV should not be None"
    assert len(obv) == 30

    # Since price always rises, OBV should increase
    # OBV[0] = 1000, OBV[1] = 2000, ...
    assert obv.iloc[-1] > obv.iloc[0], (
        "OBV should rise in uptrend: {} > {}".format(
            obv.iloc[-1], obv.iloc[0]
        ))

    # Falling prices → OBV should decrease
    prices_down = [100.0 - i * 0.5 for i in range(30)]
    df_down = make_df(prices_down, vols_const)
    obv_down = analyzer.calculate_obv(df_down)
    assert obv_down.iloc[-1] < obv_down.iloc[0], "OBV should fall in downtrend"

    # Edge cases
    assert analyzer.calculate_obv(None) is None
    assert analyzer.calculate_obv(pd.DataFrame()) is None

    print("  OBV rising in uptrend: {:.0f}".format(obv.iloc[-1]))
    print("  OBV falling in downtrend: {:.0f}".format(obv_down.iloc[-1]))
    print("PASSED ✅\n")

    # ---- TEST 5: Volume spike ----
    print("--- TEST 5: detect_volume_spike ---")
    # Normal volumes then a spike
    spike_vols = [1000.0] * 25 + [3000.0]
    spike_series = pd.Series(spike_vols)
    spike_result = analyzer.detect_volume_spike(spike_series, threshold=2.0)

    assert spike_result["is_spike"] is True, (
        "Should detect spike, got {}".format(spike_result)
    )
    assert spike_result["volume_ratio"] >= 2.0

    # No spike
    no_spike_vols = [1000.0] * 26
    no_spike_result = analyzer.detect_volume_spike(
        pd.Series(no_spike_vols), threshold=2.0
    )
    assert no_spike_result["is_spike"] is False

    # Edge case
    assert analyzer.detect_volume_spike(None)["is_spike"] is False

    print("  Spike detection working")
    print("PASSED ✅\n")

    # ---- TEST 6: Volume trend ----
    print("--- TEST 6: detect_volume_trend ---")
    # Increasing volume
    vol_increasing = pd.Series([float(500 + i * 100) for i in range(30)])
    trend = analyzer.detect_volume_trend(vol_increasing, periods=10)
    assert trend == "INCREASING", "Expected INCREASING, got {}".format(trend)

    # Decreasing volume
    vol_decreasing = pd.Series([float(3000 - i * 100) for i in range(30)])
    trend = analyzer.detect_volume_trend(vol_decreasing, periods=10)
    assert trend == "DECREASING", "Expected DECREASING, got {}".format(trend)

    # Stable volume
    vol_stable = pd.Series([1000.0] * 30)
    trend = analyzer.detect_volume_trend(vol_stable, periods=10)
    assert trend == "STABLE", "Expected STABLE, got {}".format(trend)

    print("  Volume trend detection working")
    print("PASSED ✅\n")

    # ---- TEST 7: Volume climax ----
    print("--- TEST 7: detect_volume_climax ---")
    # Selling climax: price at lows + extreme volume
    climax_prices = [100.0 - i * 0.3 for i in range(30)]
    climax_vols = [1000.0] * 25 + [5000.0] * 5
    df_climax = make_df(climax_prices, climax_vols)
    result = analyzer.detect_volume_climax(df_climax)
    print("  Climax result: {}".format(result))

    # Edge case
    assert analyzer.detect_volume_climax(None) == "NONE"
    assert analyzer.detect_volume_climax(pd.DataFrame()) == "NONE"

    print("PASSED ✅\n")

    # ---- TEST 8: Accumulation/Distribution ----
    print("--- TEST 8: calculate_accumulation_distribution ---")
    # Price closing near highs → accumulation
    ad_prices = [100.0 + i * 0.5 for i in range(30)]
    df_ad = make_df(ad_prices, high_offset=1.001, low_offset=0.999)
    ad_line = analyzer.calculate_accumulation_distribution(df_ad)

    assert ad_line is not None
    assert len(ad_line) == 30

    # Edge cases
    assert analyzer.calculate_accumulation_distribution(None) is None
    assert analyzer.calculate_accumulation_distribution(pd.DataFrame()) is None

    print("  A/D line calculated | Last: {:.2f}".format(ad_line.iloc[-1]))
    print("PASSED ✅\n")

    # ---- TEST 9: Volume-price confirmation ----
    print("--- TEST 9: volume_price_confirmation ---")
    # Bullish: price rising + volume rising
    bull_prices = [100.0 + i * 0.5 for i in range(30)]
    bull_vols = [1000.0 + i * 50 for i in range(30)]
    df_bull = make_df(bull_prices, bull_vols)
    result = analyzer.volume_price_confirmation(df_bull)
    assert result == "CONFIRMED_BULLISH", (
        "Expected CONFIRMED_BULLISH, got {}".format(result)
    )

    # Bearish: price falling + volume rising
    bear_prices = [100.0 - i * 0.5 for i in range(30)]
    bear_vols = [1000.0 + i * 50 for i in range(30)]
    df_bear = make_df(bear_prices, bear_vols)
    result = analyzer.volume_price_confirmation(df_bear)
    assert result == "CONFIRMED_BEARISH", (
        "Expected CONFIRMED_BEARISH, got {}".format(result)
    )

    # Edge case
    assert analyzer.volume_price_confirmation(None) == "NEUTRAL"

    print("  Confirmation detection working")
    print("PASSED ✅\n")

    # ---- TEST 10: Full analyze() — Bullish market ----
    print("--- TEST 10: analyze() bullish market ---")
    bull_p = [100.0 + i * 0.8 for i in range(50)]
    bull_v = [1000.0 + i * 30 for i in range(50)]
    df_bull_full = make_df(bull_p, bull_v)
    result = analyzer.analyze(df_bull_full)

    assert result is not None
    assert result["brain"] == "VOLUME"
    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert 0 <= result["confidence"] <= 100
    assert "current_volume" in result
    assert "avg_volume" in result
    assert "volume_ratio" in result
    assert "obv_trend" in result
    assert "spike" in result["details"]
    assert "trend" in result["details"]
    assert "climax" in result["details"]
    assert "confirmation" in result["details"]
    assert "ad_trend" in result["details"]

    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  Vol Ratio  : {:.2f}x".format(result["volume_ratio"]))
    print("  OBV Trend  : {}".format(result["obv_trend"]))
    print("PASSED ✅\n")

    # ---- TEST 11: Full analyze() — Bearish market ----
    print("--- TEST 11: analyze() bearish market ---")
    bear_p = [150.0 - i * 0.8 for i in range(50)]
    bear_v = [1000.0 + i * 30 for i in range(50)]
    df_bear_full = make_df(bear_p, bear_v)
    result = analyzer.analyze(df_bear_full)

    assert result["brain"] == "VOLUME"
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("PASSED ✅\n")

    # ---- TEST 12: Full analyze() — Low volume ----
    print("--- TEST 12: analyze() low volume market ---")
    low_p = [100.0 + np.sin(i * 0.3) * 2 for i in range(50)]
    low_v = [100.0] * 50  # Very low, constant
    df_low = make_df(low_p, low_v)
    result = analyzer.analyze(df_low)

    assert result["brain"] == "VOLUME"
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  (Low volume should give NEUTRAL or low confidence)")
    print("PASSED ✅\n")

    # ---- TEST 13: Edge — Insufficient data ----
    print("--- TEST 13: Insufficient data ---")
    tiny = make_df([100.0 + i for i in range(15)])
    result = analyzer.analyze(tiny)
    assert result["direction"] == "NEUTRAL"
    assert result["confidence"] == 0
    print("  Correctly returned NEUTRAL")
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
    result = analyzer.analyze(df_bull_full)

    required = [
        "brain", "direction", "confidence",
        "current_volume", "avg_volume", "volume_ratio",
        "obv_trend", "details",
    ]
    for key in required:
        assert key in result, "Missing key: {}".format(key)

    detail_keys = ["spike", "trend", "climax", "confirmation", "ad_trend"]
    for key in detail_keys:
        assert key in result["details"], "Missing detail: {}".format(key)

    print("  All {} keys present".format(
        len(required) + len(detail_keys)
    ))
    print("PASSED ✅\n")

    # ---- FINAL SUMMARY ----
    print("=" * 55)
    print("   ALL 15 TESTS PASSED ✅✅✅")
    print("=" * 55)


if __name__ == "__main__":
    run_tests()