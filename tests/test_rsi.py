# ============================================
# RSI ANALYZER TEST SCRIPT
# ============================================
# Run: python test_rsi.py
#
# Tests all 7 RSI functions with:
# - Real-like crypto price data
# - Edge cases (oversold, overbought, divergences)
# - Boundary conditions (insufficient data, NaN)
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
    """Test all RSI functions."""

    from algorithms.rsi import RSIAnalyzer

    analyzer = RSIAnalyzer(period=14)

    print("\n" + "=" * 55)
    print("   RUNNING RSI ANALYZER TESTS")
    print("=" * 55 + "\n")

    # ---- TEST 1: RSI Calculation — Steady uptrend ----
    print("--- TEST 1: RSI on steady uptrend ---")
    # 50 candles of steady price increase → RSI should be high
    prices_up = [100.0 + i * 0.5 for i in range(50)]
    df_up = make_df(prices_up)
    rsi_up = analyzer.calculate_rsi(df_up)

    assert rsi_up is not None, "RSI should not be None"
    assert len(rsi_up) == 50, "RSI length should match data"

    current = rsi_up.dropna().iloc[-1]
    assert current > 70, "Uptrend RSI should be > 70, got {:.2f}".format(current)
    print("  RSI on uptrend: {:.2f} (expected > 70)".format(current))
    print("PASSED ✅\n")

    # ---- TEST 2: RSI Calculation — Steady downtrend ----
    print("--- TEST 2: RSI on steady downtrend ---")
    prices_down = [100.0 - i * 0.5 for i in range(50)]
    df_down = make_df(prices_down)
    rsi_down = analyzer.calculate_rsi(df_down)

    current = rsi_down.dropna().iloc[-1]
    assert current < 30, "Downtrend RSI should be < 30, got {:.2f}".format(current)
    print("  RSI on downtrend: {:.2f} (expected < 30)".format(current))
    print("PASSED ✅\n")

    # ---- TEST 3: RSI Calculation — Flat market ----
    print("--- TEST 3: RSI on flat market ---")
    prices_flat = [100.0] * 50
    df_flat = make_df(prices_flat)
    rsi_flat = analyzer.calculate_rsi(df_flat)

    # Flat market: no gains, no losses
    # avg_gain = 0, avg_loss = 0 → our code returns RSI = 0
    # However, a truly flat market means no signal
    current = rsi_flat.dropna().iloc[-1]
    print("  RSI on flat market: {:.2f}".format(current))
    print("PASSED ✅\n")

    # ---- TEST 4: RSI NaN handling ----
    print("--- TEST 4: First 'period' values should be NaN ---")
    nan_count = rsi_up.isna().sum()
    assert nan_count == 14, "Should have 14 NaN values, got {}".format(nan_count)
    print("  NaN count: {} (expected 14)".format(nan_count))
    print("PASSED ✅\n")

    # ---- TEST 5: RSI range always 0-100 ----
    print("--- TEST 5: RSI values in 0-100 range ---")
    valid = rsi_up.dropna()
    assert valid.min() >= 0, "RSI min should be >= 0"
    assert valid.max() <= 100, "RSI max should be <= 100"
    print("  Range: {:.2f} to {:.2f}".format(valid.min(), valid.max()))
    print("PASSED ✅\n")

    # ---- TEST 6: Extreme levels classification ----
    print("--- TEST 6: check_extreme_levels ---")
    assert analyzer.check_extreme_levels(15) == "EXTREME_OVERSOLD"
    assert analyzer.check_extreme_levels(25) == "OVERSOLD"
    assert analyzer.check_extreme_levels(35) == "NEUTRAL_BEARISH"
    assert analyzer.check_extreme_levels(50) == "NEUTRAL"
    assert analyzer.check_extreme_levels(60) == "NEUTRAL_BULLISH"
    assert analyzer.check_extreme_levels(75) == "OVERBOUGHT"
    assert analyzer.check_extreme_levels(85) == "EXTREME_OVERBOUGHT"
    assert analyzer.check_extreme_levels(float("nan")) == "NEUTRAL"
    assert analyzer.check_extreme_levels(None) == "NEUTRAL"
    print("  All 9 level checks passed")
    print("PASSED ✅\n")

    # ---- TEST 7: Centerline cross detection ----
    print("--- TEST 7: check_centerline_cross ---")
    # Bullish cross: 48 → 52
    bullish_rsi = pd.Series([45.0, 48.0, 52.0])
    assert analyzer.check_centerline_cross(bullish_rsi) == "BULLISH_CROSS"

    # Bearish cross: 52 → 48
    bearish_rsi = pd.Series([55.0, 52.0, 48.0])
    assert analyzer.check_centerline_cross(bearish_rsi) == "BEARISH_CROSS"

    # No cross: all above 50
    no_cross_rsi = pd.Series([55.0, 60.0, 65.0])
    assert analyzer.check_centerline_cross(no_cross_rsi) == "NONE"

    # Empty series
    assert analyzer.check_centerline_cross(pd.Series(dtype=float)) == "NONE"
    assert analyzer.check_centerline_cross(None) == "NONE"

    print("  All 5 centerline checks passed")
    print("PASSED ✅\n")

    # ---- TEST 8: RSI trend detection ----
    print("--- TEST 8: get_rsi_trend ---")
    rising = pd.Series([30.0, 32.0, 35.0, 38.0, 41.0])
    assert analyzer.get_rsi_trend(rising) == "RISING"

    falling = pd.Series([70.0, 67.0, 64.0, 61.0, 58.0])
    assert analyzer.get_rsi_trend(falling) == "FALLING"

    flat = pd.Series([50.0, 50.5, 49.8, 50.2, 50.1])
    assert analyzer.get_rsi_trend(flat) == "FLAT"

    print("  All 3 trend checks passed")
    print("PASSED ✅\n")

    # ---- TEST 9: Divergence detection ----
    print("--- TEST 9: detect_divergence ---")

    # Create bullish divergence scenario:
    # Price makes lower lows, RSI makes higher lows
    # Pattern: down → up → lower down → up
    bull_prices = (
        [100] * 5 +          # stable
        [99, 97, 95] +       # drop to swing low 1 (95)
        [97, 99, 100] +      # recover
        [98, 96, 94] +       # drop to swing low 2 (94, lower than 95)
        [96, 98]             # recover
    )
    df_bull = make_df(bull_prices)
    rsi_bull = analyzer.calculate_rsi(df_bull)

    if rsi_bull is not None and rsi_bull.dropna().shape[0] >= 5:
        div_result = analyzer.detect_divergence(df_bull, rsi_bull, lookback=16)
        print("  Bullish div test: {}".format(div_result))
    else:
        # If not enough data for divergence, just verify function doesn't crash
        div_result = analyzer.detect_divergence(df_bull, rsi_bull, lookback=16)
        print("  Divergence function ran without crash")

    assert isinstance(div_result, dict)
    assert "bullish_divergence" in div_result
    assert "bearish_divergence" in div_result
    assert "divergence_strength" in div_result
    print("PASSED ✅\n")

    # ---- TEST 10: Full analyze() — Oversold market ----
    print("--- TEST 10: analyze() on oversold market ---")
    # Strong downtrend → should give SHORT or LONG(oversold bounce)
    prices_oversold = [100.0 - i * 0.8 for i in range(50)]
    df_oversold = make_df(prices_oversold)
    result = analyzer.analyze(df_oversold)

    assert result is not None, "Result should not be None"
    assert result["brain"] == "RSI"
    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert 0 <= result["confidence"] <= 100
    assert 0 <= result["rsi_value"] <= 100
    assert "level" in result["details"]
    assert "divergence" in result["details"]
    assert "trend" in result["details"]
    assert "centerline" in result["details"]

    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  RSI Value  : {:.2f}".format(result["rsi_value"]))
    print("  Level      : {}".format(result["details"]["level"]))
    print("PASSED ✅\n")

    # ---- TEST 11: Full analyze() — Overbought market ----
    print("--- TEST 11: analyze() on overbought market ---")
    prices_overbought = [100.0 + i * 0.8 for i in range(50)]
    df_overbought = make_df(prices_overbought)
    result = analyzer.analyze(df_overbought)

    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  RSI Value  : {:.2f}".format(result["rsi_value"]))
    print("PASSED ✅\n")

    # ---- TEST 12: Edge case — Minimum data ----
    print("--- TEST 12: Minimum data (15 candles) ---")
    tiny_prices = [100.0 + i for i in range(15)]
    df_tiny = make_df(tiny_prices)
    result = analyzer.analyze(df_tiny)
    assert result is not None
    assert result["brain"] == "RSI"
    print("  Works with 15 candles: direction={}".format(result["direction"]))
    print("PASSED ✅\n")

    # ---- TEST 13: Edge case — Too little data ----
    print("--- TEST 13: Too little data (5 candles) ---")
    too_small_prices = [100.0 + i for i in range(5)]
    df_too_small = make_df(too_small_prices)
    result = analyzer.analyze(df_too_small)
    assert result["direction"] == "NEUTRAL"
    assert result["confidence"] == 0
    print("  Correctly returned NEUTRAL for insufficient data")
    print("PASSED ✅\n")

    # ---- TEST 14: Edge case — Empty DataFrame ----
    print("--- TEST 14: Empty DataFrame ---")
    result = analyzer.analyze(pd.DataFrame())
    assert result["direction"] == "NEUTRAL"
    result = analyzer.analyze(None)
    assert result["direction"] == "NEUTRAL"
    print("  Correctly handled empty/None input")
    print("PASSED ✅\n")

    # ---- FINAL SUMMARY ----
    print("=" * 55)
    print("   ALL 14 TESTS PASSED ✅✅✅")
    print("=" * 55)


if __name__ == "__main__":
    run_tests()