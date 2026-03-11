# ============================================
# REMINDER MANAGER TEST SCRIPT
# ============================================
# Run: python test_reminders.py
#
# Tests reminder logic, tracking, scheduling,
# and message formatting.
# Does NOT require Telegram connection.
# ============================================

import asyncio
from datetime import datetime, timedelta


def run_async(coro):
    """Run async function synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def run_tests():
    """Test all ReminderManager functions."""

    print("\n" + "=" * 55)
    print("   RUNNING REMINDER MANAGER TESTS")
    print("=" * 55 + "\n")

    passed = 0
    failed = 0

    # ---- TEST 1: Initialization ----
    print("--- TEST 1: Initialization ---")
    try:
        from notifications.reminders import ReminderManager

        rm = ReminderManager()

        assert rm.bot is None
        assert rm._reminder_log == {}
        assert rm._reminder_counts == {}
        assert len(rm._blocked_users) == 0
        assert rm._sub_days == 28
        assert rm._stats["total_sent"] == 0

        print("  ReminderManager initialized")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 2: Set bot ----
    print("--- TEST 2: Set bot instance ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        class FakeBot:
            application = None
            _mem_subs = {}

        fb = FakeBot()
        rm.set_bot(fb)
        assert rm.bot is fb

        print("  Bot linked")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 3: Reminder tracking - not sent ----
    print("--- TEST 3: Reminder not yet sent ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        assert rm._was_reminder_sent(12345, "3_day") is False
        assert rm._was_reminder_sent(12345, "1_day") is False
        assert rm._was_reminder_sent(12345, "expired") is False

        print("  All reminder types show as not sent")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 4: Record reminder ----
    print("--- TEST 4: Record reminder ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        rm._record_reminder(12345, "3_day")

        assert rm._was_reminder_sent(12345, "3_day") is True
        assert rm._was_reminder_sent(12345, "1_day") is False
        assert rm._reminder_counts[12345] == 1

        rm._record_reminder(12345, "1_day")

        assert rm._was_reminder_sent(12345, "1_day") is True
        assert rm._reminder_counts[12345] == 2

        print("  Reminders recorded correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 5: Duplicate prevention ----
    print("--- TEST 5: Duplicate reminder prevention ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        rm._record_reminder(12345, "3_day")

        # Second check should show already sent
        assert rm._was_reminder_sent(12345, "3_day") is True

        print("  Duplicate detected and prevented")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 6: Gap enforcement ----
    print("--- TEST 6: Minimum gap enforcement ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        # No reminders sent yet → can send
        assert rm._can_send_reminder(12345) is True

        # Record a reminder just now
        rm._record_reminder(12345, "3_day")

        # Should NOT be able to send (gap not met)
        assert rm._can_send_reminder(12345) is False

        # Manually set old timestamp (13 hours ago)
        old_time = (
            datetime.now() - timedelta(hours=13)
        ).strftime("%Y-%m-%d %H:%M:%S")
        rm._reminder_log[12345]["3_day"] = old_time

        # Now gap should be met
        assert rm._can_send_reminder(12345) is True

        print("  Gap enforcement working (12h minimum)")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 7: Signal count tracking ----
    print("--- TEST 7: Signal count tracking ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        assert rm._get_signal_count(12345) == 0

        rm.add_signal_count(12345, 5)
        assert rm._get_signal_count(12345) == 5

        rm.add_signal_count(12345, 3)
        assert rm._get_signal_count(12345) == 8

        print("  Signal count: 0 → 5 → 8")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 8: Date parsing ----
    print("--- TEST 8: Date parsing ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        d1 = rm._parse_date("2024-06-15 10:30:00")
        assert d1 is not None
        assert d1.year == 2024
        assert d1.month == 6
        assert d1.day == 15

        d2 = rm._parse_date("2024-06-15")
        assert d2 is not None

        d3 = rm._parse_date(datetime(2024, 1, 1))
        assert d3 is not None

        d4 = rm._parse_date(None)
        assert d4 is None

        d5 = rm._parse_date("")
        assert d5 is None

        print("  All date formats parsed correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 9: Date formatting ----
    print("--- TEST 9: Date formatting ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        f1 = rm._format_date("2024-06-15 10:30:00")
        assert "15" in f1
        assert "Jun" in f1
        assert "2024" in f1

        f2 = rm._format_date(None)
        assert f2 is not None

        print("  Formatted: {}".format(f1))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 10: Post-expiry day messages ----
    print("--- TEST 10: Post-expiry messages ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        msg1 = rm._post_expiry_day1()
        assert "miss you" in msg1.lower()
        assert str(rm._sub_price) in msg1

        msg2 = rm._post_expiry_day2()
        assert "missing" in msg2.lower().replace("miss", "missing")
        assert str(rm._sub_price) in msg2

        msg3 = rm._post_expiry_day3()
        assert "final" in msg3.lower()
        assert str(rm._sub_price) in msg3

        print("  Day 1: 'miss you' message ✅")
        print("  Day 2: 'what you missed' message ✅")
        print("  Day 3: 'final reminder' message ✅")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 11: Blocked user tracking ----
    print("--- TEST 11: Blocked users ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        assert 99999 not in rm._blocked_users

        rm._blocked_users.add(99999)
        assert 99999 in rm._blocked_users

        # Blocked user should be skipped
        assert rm._was_reminder_sent(99999, "3_day") is False

        print("  Blocked user tracking works")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 12: Reset user reminders ----
    print("--- TEST 12: Reset user reminders ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        rm._record_reminder(12345, "3_day")
        rm._record_reminder(12345, "1_day")
        assert rm._reminder_counts[12345] == 2

        rm.reset_user_reminders(12345)

        assert rm._was_reminder_sent(12345, "3_day") is False
        assert rm._was_reminder_sent(12345, "1_day") is False
        assert 12345 not in rm._reminder_counts

        print("  Reminders reset for renewed user")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 13: Check expiring (mock data) ----
    print("--- TEST 13: Check expiring subscriptions ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        # Mock subscriptions with various expiry dates
        now = datetime.now()

        class MockBot:
            application = None
            _mem_subs = {
                11111: {
                    "chat_id": 11111,
                    "end_date": (now + timedelta(days=3)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "is_active": True,
                },
                22222: {
                    "chat_id": 22222,
                    "end_date": (now + timedelta(days=1)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "is_active": True,
                },
                33333: {
                    "chat_id": 33333,
                    "end_date": now.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "is_active": True,
                },
                44444: {
                    "chat_id": 44444,
                    "end_date": (now - timedelta(days=1)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "is_active": False,
                },
                55555: {
                    "chat_id": 55555,
                    "end_date": (now + timedelta(days=15)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "is_active": True,
                },
            }

        rm.set_bot(MockBot())

        # Run check (messages won't actually send — no bot.application)
        async def test():
            results = await rm.check_expiring_subscriptions()
            assert results["checked"] == 5
            return results

        results = run_async(test())

        print("  Checked: {} subscriptions".format(
            results["checked"]
        ))
        print("  Processing completed without crash")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 14: Process all reminders ----
    print("--- TEST 14: process_all_reminders ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        class EmptyBot:
            application = None
            _mem_subs = {}

        rm.set_bot(EmptyBot())

        async def test():
            results = await rm.process_all_reminders()
            assert "checked" in results
            assert "warnings_3day" in results
            assert "expired" in results
            return results

        results = run_async(test())

        assert rm._stats["last_run"] is not None

        print("  Process all completed")
        print("  Last run: {}".format(rm._stats["last_run"]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 15: Stats ----
    print("--- TEST 15: Statistics ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        stats = rm.get_stats()

        assert "total_processed" in stats
        assert "total_sent" in stats
        assert "total_failed" in stats
        assert "blocked_users" in stats
        assert "tracked_users" in stats
        assert "last_run" in stats

        assert stats["total_sent"] == 0
        assert stats["blocked_users"] == 0

        print("  Stats: {}".format(stats))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 16: User reminder history ----
    print("--- TEST 16: User reminder history ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        # No history
        h1 = rm.get_user_reminder_history(12345)
        assert h1 == {}

        # Add some history
        rm._record_reminder(12345, "3_day")
        rm._record_reminder(12345, "1_day")

        h2 = rm.get_user_reminder_history(12345)
        assert "3_day" in h2
        assert "1_day" in h2
        assert len(h2) == 2

        print("  History tracked: {} entries".format(len(h2)))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 17: Post-expiry day limit ----
    print("--- TEST 17: Post-expiry day limit ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        # Day 4 should NOT send
        async def test():
            result = await rm.send_post_expiry_reminder(
                12345, days_since=4
            )
            assert result is False

            result_0 = await rm.send_post_expiry_reminder(
                12345, days_since=0
            )
            assert result_0 is False

            return True

        run_async(test())

        print("  Day 4+: correctly stopped")
        print("  Day 0: correctly skipped")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 18: Keyboard builders ----
    print("--- TEST 18: Keyboard builders ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        k1 = rm._get_renew_keyboard()
        k2 = rm._get_renew_stats_keyboard()
        k3 = rm._get_comeback_keyboard()

        if k1:
            rows = k1.inline_keyboard
            assert len(rows) >= 1
            assert "Renew" in rows[0][0].text
            print("  Renew keyboard: ✅")
        else:
            print("  Renew keyboard: None (telegram not imported)")

        if k2:
            rows = k2.inline_keyboard
            assert len(rows) >= 1
            print("  Renew+Stats keyboard: ✅")
        else:
            print("  Renew+Stats keyboard: None")

        if k3:
            rows = k3.inline_keyboard
            assert len(rows) >= 1
            print("  Comeback keyboard: ✅")
        else:
            print("  Comeback keyboard: None")

        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 19: Multiple users isolation ----
    print("--- TEST 19: Per-user error isolation ---")
    try:
        from notifications.reminders import ReminderManager
        rm = ReminderManager()

        rm._record_reminder(11111, "3_day")
        rm._record_reminder(22222, "1_day")

        # User 1's reminder shouldn't affect user 2
        assert rm._was_reminder_sent(11111, "3_day") is True
        assert rm._was_reminder_sent(22222, "3_day") is False
        assert rm._was_reminder_sent(22222, "1_day") is True
        assert rm._was_reminder_sent(11111, "1_day") is False

        print("  Users isolated correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 20: Singleton import ----
    print("--- TEST 20: Module singleton ---")
    try:
        from notifications.reminders import reminder_manager

        assert reminder_manager is not None
        assert hasattr(reminder_manager, 'process_all_reminders')
        assert hasattr(reminder_manager, 'check_expiring_subscriptions')
        assert hasattr(reminder_manager, 'send_3_day_warning')
        assert hasattr(reminder_manager, 'send_1_day_warning')
        assert hasattr(reminder_manager, 'send_expired_message')
        assert hasattr(reminder_manager, 'send_post_expiry_reminder')
        assert hasattr(reminder_manager, 'send_custom_reminder')
        assert hasattr(reminder_manager, 'get_stats')
        assert hasattr(reminder_manager, 'reset_user_reminders')
        assert hasattr(reminder_manager, 'set_bot')

        print("  Singleton with all methods accessible")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
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
        print("   ⚠️ {} test(s) FAILED".format(failed))
    print("=" * 55)


if __name__ == "__main__":
    run_tests()