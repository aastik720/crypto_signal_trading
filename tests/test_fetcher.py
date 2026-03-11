# ============================================
# FETCHER TEST SCRIPT
# ============================================
# Run: python test_fetcher.py
# Tests all REST API functions against live Binance.
# Requires internet connection.
# ============================================

import asyncio


async def run_tests():
    """Test all fetcher operations against live Binance API."""

    from data.fetcher import fetcher

    print("\n" + "=" * 55)
    print("   RUNNING FETCHER TESTS (LIVE BINANCE)")
    print("=" * 55 + "\n")

    # ---- TEST 1: Get Klines ----
    print("--- TEST 1: get_klines (BTCUSDT) ---")
    df = await fetcher.get_klines("BTCUSDT", "5m", 50)
    assert df is not None, "Klines should not be None"
    assert len(df) > 0, "Klines should have data"
    assert "open" in df.columns, "Should have 'open' column"
    assert "close" in df.columns, "Should have 'close' column"
    assert df["close"].dtype == float, "Close should be float"
    print("  Rows: {} | Columns: {}".format(len(df), list(df.columns)))
    print("  Latest close: ${:,.2f}".format(df["close"].iloc[-1]))
    print("PASSED ✅\n")

    # ---- TEST 2: Get Current Price ----
    print("--- TEST 2: get_current_price (ETHUSDT) ---")
    price = await fetcher.get_current_price("ETHUSDT")
    assert price is not None, "Price should not be None"
    assert price > 0, "Price should be positive"
    print("  ETH Price: ${:,.2f}".format(price))
    print("PASSED ✅\n")

    # ---- TEST 3: Price Cache ----
    print("--- TEST 3: Price cache (should be instant) ---")
    import time
    start = time.time()
    cached_price = await fetcher.get_current_price("ETHUSDT")
    elapsed = time.time() - start
    assert cached_price is not None
    assert cached_price == price, "Cached price should match"
    assert elapsed < 0.1, "Cache should respond in < 100ms"
    print("  Cached price: ${:,.2f} (took {:.4f}s)".format(
        cached_price, elapsed
    ))
    print("PASSED ✅\n")

    # ---- TEST 4: Get Latest Price (sync) ----
    print("--- TEST 4: get_latest_price (sync) ---")
    latest = fetcher.get_latest_price("ETHUSDT")
    assert latest is not None, "Should have cached price"
    assert latest > 0
    print("  Latest ETH: ${:,.2f}".format(latest))
    print("PASSED ✅\n")

    # ---- TEST 5: Fetch Data for Analysis ----
    print("--- TEST 5: fetch_data_for_analysis (BTCUSDT) ---")
    analysis_df = await fetcher.fetch_data_for_analysis("BTCUSDT")
    assert analysis_df is not None, "Analysis data should not be None"
    assert len(analysis_df) >= 30, "Need at least 30 candles"
    expected_cols = ["open", "high", "low", "close", "volume"]
    for col in expected_cols:
        assert col in analysis_df.columns, "Missing column: {}".format(col)
        assert analysis_df[col].dtype == float, "{} should be float".format(col)
    assert analysis_df.index.name == "timestamp"
    print("  Rows: {} | Columns: {}".format(
        len(analysis_df), list(analysis_df.columns)
    ))
    print("  Index type: {}".format(type(analysis_df.index[0])))
    print("PASSED ✅\n")

    # ---- TEST 6: Get All Pairs Data ----
    print("--- TEST 6: get_all_pairs_data (all 10 pairs) ---")
    print("  This will take ~5 seconds (rate limit delays)...")
    all_data = await fetcher.get_all_pairs_data()
    assert len(all_data) > 0, "Should have at least some data"
    print("  Fetched {}/{} pairs".format(
        len(all_data), len(fetcher.trading_pairs)
    ))
    for symbol, sym_df in all_data.items():
        print("    {} : {} candles | Close: ${:,.4f}".format(
            symbol, len(sym_df), sym_df["close"].iloc[-1]
        ))
    print("PASSED ✅\n")

    # ---- TEST 7: Invalid Symbol ----
    print("--- TEST 7: Invalid symbol handling ---")
    bad_df = await fetcher.get_klines("INVALIDPAIR123", "5m", 10)
    assert bad_df is None, "Invalid symbol should return None"
    print("  Correctly returned None for invalid symbol")
    print("PASSED ✅\n")

    # ---- TEST 8: WebSocket (3 seconds) ----
    print("--- TEST 8: WebSocket (3 second test) ---")
    received_prices = {}

    async def test_callback(candle_data):
        """Captures candle data from WebSocket."""
        received_prices[candle_data["symbol"]] = candle_data["close"]

    # Start WebSocket in background
    ws_task = asyncio.create_task(
        fetcher.start_websocket(test_callback)
    )

    # Let it run for 3 seconds
    await asyncio.sleep(3)

    # Check if prices are being received
    prices_count = len(fetcher.latest_prices)
    print("  Received prices for {} pairs in 3 seconds".format(
        prices_count
    ))
    if prices_count > 0:
        for sym, px in list(fetcher.latest_prices.items())[:3]:
            print("    {} : ${:,.2f}".format(sym, px))

    # Stop WebSocket
    await fetcher.stop_websocket()
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass
    print("  WebSocket stopped cleanly")
    print("PASSED ✅\n")

    # ---- CLEANUP ----
    await fetcher.close()

    # ---- FINAL SUMMARY ----
    print("=" * 55)
    print("   ALL 8 TESTS PASSED ✅✅✅")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(run_tests())