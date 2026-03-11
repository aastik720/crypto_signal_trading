# ============================================
# MAIN.PY INTEGRATION TEST
# ============================================
# Runs ONE signal cycle to verify all modules
# are properly linked and working together.
#
# Run: python test_main.py
# ============================================

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_integration():
    """Run one cycle to verify all modules work together."""

    print("\n" + "=" * 55)
    print("   INTEGRATION TEST — ONE SIGNAL CYCLE")
    print("=" * 55 + "\n")

    # ---- Step 1: Import all modules ----
    print("--- Step 1: Importing modules ---")
    from config.settings import Config
    from database.db_manager import db
    from data.fetcher import fetcher
    from algorithms.rsi import rsi_analyzer
    print("✅ All modules imported\n")

    # ---- Step 2: Initialize database ----
    print("--- Step 2: Initialize database ---")
    result = await db.create_tables()
    assert result is True, "Table creation failed"
    print("✅ Database ready\n")

    # ---- Step 3: Fetch data for ONE pair ----
    print("--- Step 3: Fetch BTC data ---")
    df = await fetcher.fetch_data_for_analysis("BTCUSDT")
    assert df is not None, "Data fetch failed"
    assert len(df) >= 30, "Need 30+ candles"
    print("✅ Got {} candles\n".format(len(df)))

    # ---- Step 4: Run RSI analysis ----
    print("--- Step 4: Run RSI analysis ---")
    rsi_result = rsi_analyzer.analyze(df)
    assert rsi_result is not None
    assert rsi_result["brain"] == "RSI"
    assert rsi_result["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert 0 <= rsi_result["confidence"] <= 100
    print("✅ RSI: {} | {:.1f}% confidence | RSI={:.2f}\n".format(
        rsi_result["direction"],
        rsi_result["confidence"],
        rsi_result["rsi_value"]
    ))

    # ---- Step 5: Log signal to database ----
    print("--- Step 5: Log signal to database ---")
    price = await fetcher.get_current_price("BTCUSDT")
    signal_id = await db.log_signal(
        pair="BTCUSDT",
        direction=rsi_result["direction"],
        entry_price=price or 0,
        target_1=(price or 0) * 1.015,
        target_2=(price or 0) * 1.030,
        stop_loss=(price or 0) * 0.990,
        confidence=rsi_result["confidence"],
        sent_public=False,
        sent_private=False,
    )
    assert signal_id is not None
    print("✅ Signal #{} logged to database\n".format(signal_id))

    # ---- Step 6: Check database stats ----
    print("--- Step 6: Database stats ---")
    stats = await db.get_signal_stats()
    print("✅ Total signals: {} | Pending: {}\n".format(
        stats["total_signals"], stats["pending"]
    ))

    # ---- Step 7: Test full bot cycle ----
    print("--- Step 7: Full bot cycle (3 pairs only) ---")
    from main import CryptoSignalBot
    test_bot = CryptoSignalBot()
    test_bot.brains_active = ["RSI"]

    # Temporarily reduce pairs for faster test
    original_pairs = Config.TRADING_PAIRS
    Config.TRADING_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    signals = await test_bot.run_signal_cycle()
    print("✅ Cycle produced {} signals\n".format(len(signals)))

    # Restore original pairs
    Config.TRADING_PAIRS = original_pairs

    # ---- Cleanup ----
    await fetcher.close()

    # ---- Final ----
    print("=" * 55)
    print("   INTEGRATION TEST PASSED ✅✅✅")
    print("   All modules properly linked!")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    asyncio.run(test_integration())