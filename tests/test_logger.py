# ============================================
# LOGGER & PERFORMANCE TRACKER TEST SCRIPT
# ============================================
# Run: python test_logger.py
# ============================================

import os
import csv
from datetime import datetime


def run_tests():
    """Test all Logger and PerformanceTracker functions."""

    print("\n" + "=" * 55)
    print("   RUNNING LOGGER & PERFORMANCE TESTS")
    print("=" * 55 + "\n")

    passed = 0
    failed = 0

    # ---- TEST 1: BotLogger init ----
    print("--- TEST 1: BotLogger initialization ---")
    try:
        from utils.logger import BotLogger

        bl = BotLogger()

        assert bl._logger is not None
        assert bl._signal_logger is not None
        assert bl._log_count["info"] == 0

        print("  BotLogger initialized")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 2: Log levels ----
    print("--- TEST 2: All log levels ---")
    try:
        from utils.logger import BotLogger
        bl = BotLogger()

        bl.debug("Test debug message", module="TEST")
        bl.info("Test info message", module="TEST")
        bl.warning("Test warning message", module="TEST")
        bl.error("Test error message", module="TEST")
        bl.critical("Test critical message", module="TEST")

        stats = bl.get_log_stats()
        assert stats["debug"] >= 1
        assert stats["info"] >= 1
        assert stats["warning"] >= 1
        assert stats["error"] >= 1
        assert stats["critical"] >= 1

        print("  All 5 log levels working")
        print("  Stats: {}".format(stats))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 3: Signal logging ----
    print("--- TEST 3: Signal logging ---")
    try:
        from utils.logger import BotLogger
        bl = BotLogger()

        signal = {
            "pair": "BTC/USDT",
            "direction": "LONG",
            "confidence": 82,
            "entry_price": 67500,
            "target_1": 69000,
            "target_2": 71000,
            "stop_loss": 66500,
            "agreement_level": "STRONG",
            "risk_reward": 2.5,
        }

        bl.log_signal(signal)

        print("  Signal logged without error")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 4: User action logging ----
    print("--- TEST 4: User action logging ---")
    try:
        from utils.logger import BotLogger
        bl = BotLogger()

        bl.log_user_action(12345, "REGISTERED", "New user")
        bl.log_user_action(12345, "ACTIVATED_TOKEN", "CSB-****")
        bl.log_user_action(12345, "CHECKED_STATUS", "")

        print("  User actions logged")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 5: API call logging ----
    print("--- TEST 5: API call logging ---")
    try:
        from utils.logger import BotLogger
        bl = BotLogger()

        bl.log_api_call(
            "binance/klines", "SUCCESS", 150.5, "BTC/USDT 5m"
        )
        bl.log_api_call(
            "binance/klines", "FAILED", 5500, "Timeout"
        )

        print("  API calls logged (success + failure)")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 6: Error logging ----
    print("--- TEST 6: Error logging with traceback ---")
    try:
        from utils.logger import BotLogger
        bl = BotLogger()

        try:
            x = 1 / 0
        except Exception as exc:
            bl.log_error("TEST", exc, tb_info=True)

        bl.log_error("TEST", "Manual error", tb_info=None)

        print("  Errors logged with/without traceback")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 7: Payment logging ----
    print("--- TEST 7: Payment logging ---")
    try:
        from utils.logger import BotLogger
        bl = BotLogger()

        bl.log_payment(12345, "PAY_001", 999, "SUCCESS")
        bl.log_payment(12345, "PAY_002", 999, "FAILED")
        bl.log_payment(12345, "PAY_003", 999, "PENDING")

        print("  Payment events logged")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 8: Log file size ----
    print("--- TEST 8: Log file size ---")
    try:
        from utils.logger import BotLogger
        bl = BotLogger()

        size = bl.get_log_file_size()
        assert isinstance(size, float)
        assert size >= 0

        print("  Log file size: {:.2f} MB".format(size))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 9: PerformanceTracker init ----
    print("--- TEST 9: PerformanceTracker init ---")
    try:
        from utils.logger import PerformanceTracker

        pt = PerformanceTracker()

        assert pt.csv_path is not None
        assert os.path.exists(pt.csv_path)
        assert isinstance(pt._signals, dict)

        print("  Tracker initialized, CSV exists")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 10: Log new signal ----
    print("--- TEST 10: Log new signal ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        signal = {
            "pair": "BTC/USDT",
            "direction": "LONG",
            "confidence": 78,
            "entry_price": 67500,
            "target_1": 69000,
            "target_2": 71000,
            "stop_loss": 66500,
            "agreement_level": "STRONG",
            "risk_reward": 2.5,
        }

        sig_id = pt.log_new_signal(signal)

        assert sig_id is not None
        assert sig_id.startswith("SIG-")
        assert sig_id in pt._signals
        assert pt._signals[sig_id]["result"] == "PENDING"

        print("  Signal ID: {}".format(sig_id))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 11: Update signal result ----
    print("--- TEST 11: Update signal result ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        signal = {
            "pair": "ETH/USDT",
            "direction": "LONG",
            "confidence": 72,
            "entry_price": 3500,
            "target_1": 3600,
            "target_2": 3700,
            "stop_loss": 3450,
        }

        sig_id = pt.log_new_signal(signal)
        assert pt._total_pending >= 1

        result = pt.update_signal_result(
            sig_id, "WIN", pnl_percent=2.85, notes="T1 hit"
        )

        assert result is True
        assert pt._signals[sig_id]["result"] == "WIN"
        assert pt._signals[sig_id]["pnl_percent"] == "2.85"

        print("  Signal updated to WIN (+2.85%)")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 12: Win rate calculation ----
    print("--- TEST 12: Win rate calculation ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        # 3 wins, 1 loss
        for i in range(3):
            sid = pt.log_new_signal({
                "pair": "BTC/USDT", "direction": "LONG",
                "confidence": 80, "entry_price": 67000 + i * 100,
            })
            pt.update_signal_result(sid, "WIN", 2.0)

        sid = pt.log_new_signal({
            "pair": "BTC/USDT", "direction": "SHORT",
            "confidence": 70, "entry_price": 68000,
        })
        pt.update_signal_result(sid, "LOSS", -1.5)

        wr = pt.get_win_rate()
        assert wr == 75.0, "Expected 75.0%, got {}%".format(wr)

        print("  Win rate: {:.1f}% (3W/1L)".format(wr))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 13: Performance report ----
    print("--- TEST 13: Performance report ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        # Add signals
        for i in range(5):
            sid = pt.log_new_signal({
                "pair": "SOL/USDT", "direction": "LONG",
                "confidence": 75, "entry_price": 150 + i,
            })
            if i < 3:
                pt.update_signal_result(sid, "WIN", 3.0)
            else:
                pt.update_signal_result(sid, "LOSS", -1.5)

        report = pt.get_performance_report()

        assert "total_signals" in report
        assert "wins" in report
        assert "losses" in report
        assert "win_rate" in report
        assert "total_pnl" in report
        assert "pair_breakdown" in report
        assert report["total_signals"] >= 5

        print("  Report generated:")
        print("    Signals: {}".format(report["total_signals"]))
        print("    Win rate: {:.1f}%".format(report["win_rate"]))
        print("    Total PnL: {:+.2f}%".format(report["total_pnl"]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 14: Best/worst pair ----
    print("--- TEST 14: Best and worst pair ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        # BTC: 4 wins, 1 loss = 80%
        for i in range(4):
            sid = pt.log_new_signal({
                "pair": "BTC/USDT", "direction": "LONG",
                "confidence": 80, "entry_price": 67000,
            })
            pt.update_signal_result(sid, "WIN", 2.0)

        sid = pt.log_new_signal({
            "pair": "BTC/USDT", "direction": "LONG",
            "confidence": 65, "entry_price": 67500,
        })
        pt.update_signal_result(sid, "LOSS", -1.0)

        # DOGE: 1 win, 3 losses = 25%
        sid = pt.log_new_signal({
            "pair": "DOGE/USDT", "direction": "LONG",
            "confidence": 66, "entry_price": 0.08,
        })
        pt.update_signal_result(sid, "WIN", 5.0)

        for i in range(3):
            sid = pt.log_new_signal({
                "pair": "DOGE/USDT", "direction": "SHORT",
                "confidence": 68, "entry_price": 0.085,
            })
            pt.update_signal_result(sid, "LOSS", -2.0)

        best = pt.get_best_pair()
        worst = pt.get_worst_pair()

        assert "BTC" in best, "BTC should be best, got: {}".format(best)
        assert "DOGE" in worst, "DOGE should be worst, got: {}".format(worst)

        print("  Best:  {}".format(best))
        print("  Worst: {}".format(worst))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 15: Pair win rate ----
    print("--- TEST 15: Per-pair win rate ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        for i in range(3):
            sid = pt.log_new_signal({
                "pair": "ADA/USDT", "direction": "LONG",
                "confidence": 70, "entry_price": 0.5,
            })
            pt.update_signal_result(sid, "WIN", 1.5)

        sid = pt.log_new_signal({
            "pair": "ADA/USDT", "direction": "SHORT",
            "confidence": 66, "entry_price": 0.52,
        })
        pt.update_signal_result(sid, "LOSS", -0.8)

        wr = pt.get_pair_win_rate("ADA/USDT")
        assert wr == 75.0

        wr_missing = pt.get_pair_win_rate("FAKE/USDT")
        assert wr_missing == 0.0

        print("  ADA/USDT: {:.0f}%".format(wr))
        print("  FAKE/USDT: {:.0f}%".format(wr_missing))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 16: Recent signals ----
    print("--- TEST 16: Recent signals ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        for i in range(5):
            pt.log_new_signal({
                "pair": "XRP/USDT", "direction": "LONG",
                "confidence": 70 + i, "entry_price": 0.5,
            })

        recent = pt.get_recent_signals(limit=3)
        assert len(recent) == 3
        assert recent[0]["timestamp"] >= recent[1]["timestamp"]

        print("  Got {} recent signals".format(len(recent)))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 17: Formatted report ----
    print("--- TEST 17: Formatted report ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        sid = pt.log_new_signal({
            "pair": "BNB/USDT", "direction": "LONG",
            "confidence": 75, "entry_price": 600,
        })
        pt.update_signal_result(sid, "WIN", 3.0)

        report = pt.get_formatted_report()

        assert "Performance Report" in report
        assert "Win rate" in report
        assert "Total PnL" in report

        print("  Formatted report generated")
        for line in report.split("\n")[:5]:
            clean = line.replace("<b>", "").replace("</b>", "")
            clean = clean.replace("<i>", "").replace("</i>", "")
            if clean.strip():
                print("    {}".format(clean.strip()))
        print("    ...")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 18: CSV file integrity ----
    print("--- TEST 18: CSV file integrity ---")
    try:
        from utils.logger import PerformanceTracker, SIGNALS_CSV
        pt = PerformanceTracker()

        pt.log_new_signal({
            "pair": "TEST/USDT", "direction": "LONG",
            "confidence": 99, "entry_price": 1.0,
        })

        assert os.path.exists(pt.csv_path)

        with open(pt.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 1
        headers = rows[0].keys()
        assert "signal_id" in headers
        assert "pair" in headers
        assert "result" in headers

        count = pt.get_csv_row_count()
        assert count >= 1

        print("  CSV: {} rows, all columns present".format(count))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 19: Invalid update ----
    print("--- TEST 19: Invalid update handling ---")
    try:
        from utils.logger import PerformanceTracker
        pt = PerformanceTracker()

        # Non-existent signal
        result = pt.update_signal_result("SIG-FAKE", "WIN", 1.0)
        assert result is False

        # Invalid result type
        sid = pt.log_new_signal({
            "pair": "TEST/USDT", "direction": "LONG",
            "confidence": 70, "entry_price": 1.0,
        })
        result2 = pt.update_signal_result(sid, "MAYBE", 1.0)
        assert result2 is False

        print("  Invalid updates rejected correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 20: Singletons ----
    print("--- TEST 20: Module singletons ---")
    try:
        from utils.logger import bot_logger, performance_tracker

        assert bot_logger is not None
        assert performance_tracker is not None

        assert hasattr(bot_logger, 'debug')
        assert hasattr(bot_logger, 'info')
        assert hasattr(bot_logger, 'warning')
        assert hasattr(bot_logger, 'error')
        assert hasattr(bot_logger, 'critical')
        assert hasattr(bot_logger, 'log_signal')
        assert hasattr(bot_logger, 'log_user_action')
        assert hasattr(bot_logger, 'log_api_call')
        assert hasattr(bot_logger, 'log_error')
        assert hasattr(bot_logger, 'log_payment')

        assert hasattr(performance_tracker, 'log_new_signal')
        assert hasattr(performance_tracker, 'update_signal_result')
        assert hasattr(performance_tracker, 'get_win_rate')
        assert hasattr(performance_tracker, 'get_performance_report')
        assert hasattr(performance_tracker, 'get_best_pair')
        assert hasattr(performance_tracker, 'get_worst_pair')

        print("  Both singletons accessible")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ============================================
    # CLEANUP
    # ============================================
    try:
        test_csv = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "signals_history.csv"
        )
        if os.path.exists(test_csv):
            os.remove(test_csv)
            print("\n[CLEANUP] Removed test CSV")
    except Exception:
        pass

    # ============================================
    # SUMMARY
    # ============================================
    total = passed + failed
    print("=" * 55)
    print("   TEST RESULTS: {}/{} PASSED".format(passed, total))
    if failed == 0:
        print("   🎉 ALL TESTS PASSED!")
    else:
        print("   ⚠️ {} test(s) FAILED".format(failed))
    print("=" * 55)


if __name__ == "__main__":
    run_tests()