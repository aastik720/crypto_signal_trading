# ============================================
# SUPPORT & RESISTANCE TEST SCRIPT
# ============================================
# Run: python test_support_resistance.py
# ============================================

import numpy as np
import pandas as pd


def make_df(close_prices, high_prices=None, low_prices=None,
            volumes=None):
    """Helper: creates DataFrame with full OHLCV."""
    n = len(close_prices)
    if high_prices is None:
        high_prices = [p * 1.002 for p in close_prices]
    if low_prices is None:
        low_prices = [p * 0.998 for p in close_prices]
    if volumes is None:
        volumes = [1000.0 + i * 10 for i in range(n)]

    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
        "open":   [float(p) * 0.999 for p in close_prices],
        "high":   [float(h) for h in high_prices],
        "low":    [float(l) for l in low_prices],
        "close":  [float(p) for p in close_prices],
        "volume": [float(v) for v in volumes],
    })


def make_oscillating_df(center=100, amplitude=5, periods=80):
    """Creates oscillating price data with clear S/R levels."""
    close = []
    high = []
    low = []

    for i in range(periods):
        # Sine wave creates predictable highs and lows
        val = center + amplitude * np.sin(i * 0.4)
        close.append(val)
        high.append(val + 0.5)
        low.append(val - 0.5)

    return make_df(close, high, low)


def run_tests():
    """Test all S/R functions."""

    from algorithms.support_resistance import SupportResistanceAnalyzer

    analyzer = SupportResistanceAnalyzer(
        swing_lookback=3, cluster_threshold=0.5
    )

    print("\n" + "=" * 55)
    print("   RUNNING SUPPORT & RESISTANCE TESTS")
    print("=" * 55 + "\n")

    # ---- TEST 1: Find swing highs ----
    print("--- TEST 1: find_swing_highs ---")
    df_osc = make_oscillating_df(100, 5, 80)
    highs = analyzer.find_swing_highs(df_osc, lookback=3)

    assert isinstance(highs, list)
    assert len(highs) > 0, "Should find swing highs in oscillating data"

    for h in highs[:3]:
        assert "price" in h
        assert "index" in h
        assert "volume_at_level" in h
        assert h["price"] > 0

    print("  Found {} swing highs".format(len(highs)))
    print("  First: {:.2f} | Last: {:.2f}".format(
        highs[0]["price"], highs[-1]["price"]
    ))
    print("PASSED ✅\n")

    # ---- TEST 2: Find swing lows ----
    print("--- TEST 2: find_swing_lows ---")
    lows = analyzer.find_swing_lows(df_osc, lookback=3)

    assert isinstance(lows, list)
    assert len(lows) > 0, "Should find swing lows"

    for l in lows[:3]:
        assert "price" in l
        assert l["price"] > 0

    print("  Found {} swing lows".format(len(lows)))
    print("PASSED ✅\n")

    # ---- TEST 3: Swing edge cases ----
    print("--- TEST 3: Swing detection edge cases ---")
    assert analyzer.find_swing_highs(None) == []
    assert analyzer.find_swing_highs(pd.DataFrame()) == []

    tiny = make_df([100, 101, 102])
    assert analyzer.find_swing_highs(tiny, lookback=3) == []

    print("  All edge cases handled")
    print("PASSED ✅\n")

    # ---- TEST 4: Cluster levels ----
    print("--- TEST 4: cluster_levels ---")
    all_levels = highs + lows
    zones = analyzer.cluster_levels(all_levels)

    assert isinstance(zones, list)
    assert len(zones) > 0

    for z in zones:
        assert "price" in z
        assert "strength" in z
        assert "touch_count" in z
        assert z["strength"] >= 1

    # Zones should be sorted by strength (descending)
    for i in range(len(zones) - 1):
        assert zones[i]["strength"] >= zones[i + 1]["strength"]

    print("  {} zones created from {} levels".format(
        len(zones), len(all_levels)
    ))
    print("  Strongest zone: {:.2f} ({} touches)".format(
        zones[0]["price"], zones[0]["touch_count"]
    ))
    print("PASSED ✅\n")

    # ---- TEST 5: Cluster edge cases ----
    print("--- TEST 5: Cluster edge cases ---")
    assert analyzer.cluster_levels([]) == []

    single = [{"price": 100.0, "index": 0, "volume_at_level": 1000}]
    result = analyzer.cluster_levels(single)
    assert len(result) == 1

    print("  Edge cases handled")
    print("PASSED ✅\n")

    # ---- TEST 6: Classify levels ----
    print("--- TEST 6: classify_levels ---")
    current = float(df_osc["close"].iloc[-1])
    classified = analyzer.classify_levels(zones, current)

    assert "support_levels" in classified
    assert "resistance_levels" in classified

    # All support should be below current price
    for s in classified["support_levels"]:
        assert s["price"] < current, (
            "Support {} should be below price {}".format(
                s["price"], current
            ))
        assert s["type"] == "SUPPORT"

    # All resistance should be above current price
    for r in classified["resistance_levels"]:
        assert r["price"] > current, (
            "Resistance {} should be above price {}".format(
                r["price"], current
            ))
        assert r["type"] == "RESISTANCE"

    print("  Support: {} levels | Resistance: {} levels".format(
        len(classified["support_levels"]),
        len(classified["resistance_levels"])
    ))
    print("PASSED ✅\n")

    # ---- TEST 7: Nearest support/resistance ----
    print("--- TEST 7: get_nearest_support/resistance ---")
    sup = analyzer.get_nearest_support(
        classified["support_levels"], current
    )
    res = analyzer.get_nearest_resistance(
        classified["resistance_levels"], current
    )

    if sup:
        assert sup["price"] < current
        assert sup["distance_percent"] >= 0
        assert sup["strength"] >= 1
        print("  Nearest support: {:.2f} ({:.2f}% away)".format(
            sup["price"], sup["distance_percent"]
        ))

    if res:
        assert res["price"] > current
        assert res["distance_percent"] >= 0
        print("  Nearest resistance: {:.2f} ({:.2f}% away)".format(
            res["price"], res["distance_percent"]
        ))

    # Edge: empty lists
    assert analyzer.get_nearest_support([], 100) is None
    assert analyzer.get_nearest_resistance([], 100) is None

    print("PASSED ✅\n")

    # ---- TEST 8: is_at_level ----
    print("--- TEST 8: is_at_level ---")
    assert analyzer.is_at_level(100.0, 100.2, 0.3) is True
    assert analyzer.is_at_level(100.0, 101.0, 0.3) is False
    assert analyzer.is_at_level(100.0, 99.8, 0.3) is True
    assert analyzer.is_at_level(0, 100, 0.3) is False

    print("  All level proximity checks passed")
    print("PASSED ✅\n")

    # ---- TEST 9: Detect bounce ----
    print("--- TEST 9: detect_bounce ---")
    # Create support bounce: price drops to 95, bounces to 98
    bounce_close = [100, 99, 97, 95, 96, 98]
    bounce_high = [101, 100, 98, 96, 97, 99]
    bounce_low = [99, 98, 96, 94.5, 95, 97]
    df_bounce = make_df(bounce_close, bounce_high, bounce_low)

    result = analyzer.detect_bounce(df_bounce, 95.0, "SUPPORT")
    assert result["bounce_detected"] is True
    assert result["bounce_type"] == "SUPPORT_BOUNCE"
    assert result["bounce_strength"] > 0

    # Resistance rejection
    rej_close = [100, 101, 103, 105, 104, 102]
    rej_high = [101, 102, 104, 105.5, 105, 103]
    rej_low = [99, 100, 102, 104, 103, 101]
    df_rej = make_df(rej_close, rej_high, rej_low)

    result = analyzer.detect_bounce(df_rej, 105.0, "RESISTANCE")
    assert result["bounce_detected"] is True
    assert result["bounce_type"] == "RESISTANCE_REJECTION"

    # Edge cases
    assert analyzer.detect_bounce(None, 100, "SUPPORT")["bounce_detected"] is False

    print("  Bounce detection working")
    print("PASSED ✅\n")

    # ---- TEST 10: Detect breakout ----
    print("--- TEST 10: detect_breakout ---")
    # Breakout above resistance at 105
    break_close = [102, 103, 104, 106, 107]
    df_break = make_df(break_close)

    # Create fake classified levels
    fake_levels = {
        "support_levels": [],
        "resistance_levels": [
            {"price": 105.0, "strength": 3, "touch_count": 3,
             "distance_percent": 0.5, "type": "RESISTANCE",
             "calculated_strength": 50},
        ],
    }

    result = analyzer.detect_breakout(df_break, fake_levels)
    assert result["breakout_detected"] is True
    assert result["breakout_type"] == "BREAKOUT_UP"

    # Edge
    assert analyzer.detect_breakout(None, None)["breakout_detected"] is False

    print("  Breakout detection working")
    print("PASSED ✅\n")

    # ---- TEST 11: Level strength ----
    print("--- TEST 11: calculate_level_strength ---")
    test_level = {
        "touch_count": 3,
        "max_index": len(df_osc) - 5,
        "avg_volume": 2000.0,
    }
    strength = analyzer.calculate_level_strength(test_level, df_osc)
    assert 0 <= strength <= 100
    assert strength > 0
    print("  Strength: {} (3 touches, recent, with volume)".format(strength))

    # Edge: 1 touch, old
    weak = {"touch_count": 1, "max_index": 0, "avg_volume": 0}
    weak_str = analyzer.calculate_level_strength(weak, df_osc)
    assert weak_str < strength
    print("  Weak level strength: {}".format(weak_str))

    print("PASSED ✅\n")

    # ---- TEST 12: Full analyze() — oscillating ----
    print("--- TEST 12: analyze() oscillating market ---")
    result = analyzer.analyze(df_osc)

    assert result is not None
    assert result["brain"] == "SUPPORT_RESISTANCE"
    assert result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert 0 <= result["confidence"] <= 100
    assert result["current_price"] > 0
    assert "details" in result
    assert "total_support_levels" in result["details"]
    assert "total_resistance_levels" in result["details"]
    assert "bounce" in result["details"]
    assert "breakout" in result["details"]
    assert "role_reversal" in result["details"]
    assert "support_zones" in result["details"]
    assert "resistance_zones" in result["details"]
    assert "price_position" in result["details"]

    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("  Support lvls: {}".format(
        result["details"]["total_support_levels"]
    ))
    print("  Resist. lvls: {}".format(
        result["details"]["total_resistance_levels"]
    ))
    print("PASSED ✅\n")

    # ---- TEST 13: Full analyze() — uptrend ----
    print("--- TEST 13: analyze() uptrend ---")
    prices_up = [100 + i * 0.5 + np.sin(i * 0.5) * 2 for i in range(80)]
    df_up = make_df(prices_up)
    result = analyzer.analyze(df_up)
    assert result["brain"] == "SUPPORT_RESISTANCE"
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("PASSED ✅\n")

    # ---- TEST 14: Full analyze() — downtrend ----
    print("--- TEST 14: analyze() downtrend ---")
    prices_down = [150 - i * 0.5 + np.sin(i * 0.5) * 2 for i in range(80)]
    df_down = make_df(prices_down)
    result = analyzer.analyze(df_down)
    assert result["brain"] == "SUPPORT_RESISTANCE"
    print("  Direction  : {}".format(result["direction"]))
    print("  Confidence : {:.1f}%".format(result["confidence"]))
    print("PASSED ✅\n")

    # ---- TEST 15: Edge — insufficient data ----
    print("--- TEST 15: Insufficient data ---")
    tiny = make_df([100 + i for i in range(15)])
    result = analyzer.analyze(tiny)
    assert result["direction"] == "NEUTRAL"
    assert result["confidence"] == 0
    print("  Correctly returned NEUTRAL")
    print("PASSED ✅\n")

    # ---- TEST 16: Edge — empty/None ----
    print("--- TEST 16: Empty/None ---")
    assert analyzer.analyze(None)["direction"] == "NEUTRAL"
    assert analyzer.analyze(pd.DataFrame())["direction"] == "NEUTRAL"
    print("  Handled correctly")
    print("PASSED ✅\n")

    # ---- TEST 17: Result structure ----
    print("--- TEST 17: Result structure validation ---")
    r = analyzer.analyze(df_osc)

    top_keys = ["brain", "direction", "confidence",
                "current_price", "nearest_support",
                "nearest_resistance", "details"]
    for k in top_keys:
        assert k in r, "Missing: {}".format(k)

    detail_keys = [
        "total_support_levels", "total_resistance_levels",
        "at_support", "at_resistance", "bounce", "breakout",
        "role_reversal", "support_zones", "resistance_zones",
        "price_position"
    ]
    for k in detail_keys:
        assert k in r["details"], "Missing detail: {}".format(k)

    print("  All {} keys verified".format(
        len(top_keys) + len(detail_keys)
    ))
    print("PASSED ✅\n")

    # ---- FINAL SUMMARY ----
    print("=" * 55)
    print("   ALL 17 TESTS PASSED ✅✅✅")
    print("=" * 55)


if __name__ == "__main__":
    run_tests()