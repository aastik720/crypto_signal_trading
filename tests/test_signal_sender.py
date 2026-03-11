# ============================================
# SIGNAL SENDER TEST SCRIPT
# ============================================
# Run: python test_signal_sender.py
#
# Tests formatting, queue, counters, and helpers.
# Does NOT require Telegram connection.
# ============================================

from datetime import datetime, date, timedelta


def make_sample_signal(pair="BTC/USDT", direction="LONG",
                        confidence=78):
    """Create a sample signal for testing."""
    return {
        "pair": pair,
        "direction": direction,
        "entry_price": 67500.00,
        "target_1": 69000.00,
        "target_2": 71000.00,
        "stop_loss": 66500.00,
        "confidence": confidence,
        "valid_for_minutes": 10,
        "timestamp": datetime.now().strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
        "brain_details": {
            "RSI": {"direction": "LONG", "confidence": 80},
            "MACD": {"direction": "LONG", "confidence": 75},
            "BOLLINGER": {"direction": "NEUTRAL", "confidence": 0},
            "VOLUME": {"direction": "LONG", "confidence": 65},
            "EMA": {"direction": "LONG", "confidence": 70},
            "SUPPORT_RESISTANCE": {
                "direction": "LONG", "confidence": 60
            },
            "CANDLE_PATTERNS": {
                "direction": "NEUTRAL", "confidence": 0
            },
            "OBV": {"direction": "LONG", "confidence": 72},
        },
        "agreement_level": "STRONG",
        "risk_reward": 2.5,
    }


def run_tests():
    """Test all Signal Sender functions (offline)."""

    print("\n" + "=" * 55)
    print("   RUNNING SIGNAL SENDER TESTS (OFFLINE)")
    print("=" * 55 + "\n")

    passed = 0
    failed = 0

    # ---- TEST 1: Initialization ----
    print("--- TEST 1: Initialization ---")
    try:
        from bot.signal_sender import SignalSender

        sender = SignalSender()

        assert sender.bot is None
        assert sender.daily_limit == 2
        assert sender._public_count == 0
        assert sender._public_date == date.today()
        assert len(sender._signal_queue) == 0
        assert sender._is_sending is False
        assert sender._total_sent == 0

        print("  Sender initialized with defaults")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 2: Private signal formatting ----
    print("--- TEST 2: Private signal format ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        signal = make_sample_signal()
        msg = sender.format_signal_message(signal, is_public=False)

        assert "BTC/USDT" in msg
        assert "LONG" in msg
        assert "67,500" in msg
        assert "69,000" in msg
        assert "71,000" in msg
        assert "66,500" in msg
        assert "78" in msg
        assert "2.5" in msg or "2.50" in msg
        assert "STRONG" in msg
        assert "RSI" in msg
        assert "MACD" in msg
        assert "OBV" in msg
        assert "Target 2" in msg
        assert "Brain Analysis" in msg
        assert len(msg) > 200

        print("  Private format complete ({} chars)".format(len(msg)))
        for line in msg.split("\n")[:6]:
            clean = line.replace("<b>", "").replace("</b>", "")
            clean = clean.replace("<code>", "").replace("</code>", "")
            clean = clean.replace("<i>", "").replace("</i>", "")
            if clean.strip():
                print("    {}".format(clean.strip()))
        print("    ...")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 3: Public signal formatting ----
    print("--- TEST 3: Public signal format ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        signal = make_sample_signal()
        msg = sender.format_signal_message(signal, is_public=True)

        assert "FREE SIGNAL" in msg
        assert "BTC/USDT" in msg
        assert "LONG" in msg
        assert "67,500" in msg
        assert "Target 1" in msg
        assert "Premium" in msg
        assert "/2 free signals" in msg
        assert "Target 2" not in msg
        assert "Brain Analysis" not in msg

        print("  Public format: no Target 2, no Brain details")
        print("  Includes premium CTA ✅")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 4: SHORT signal formatting ----
    print("--- TEST 4: SHORT signal format ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        signal = make_sample_signal(
            pair="ETH/USDT", direction="SHORT", confidence=71
        )
        signal["entry_price"] = 3500.00
        signal["target_1"] = 3350.00
        signal["target_2"] = 3200.00
        signal["stop_loss"] = 3580.00

        msg = sender.format_signal_message(signal)

        assert "ETH/USDT" in msg
        assert "SHORT" in msg
        assert "71" in msg

        print("  SHORT signal formatted correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 5: Edge case prices ----
    print("--- TEST 5: Price formatting edge cases ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        # Large price
        assert "$67,500.00" == sender._format_price(67500)

        # Medium price
        assert "$3.4500" == sender._format_price(3.45)

        # Small price
        assert "$0.0854" == sender._format_price(0.0854)

        # Very small price
        result = sender._format_price(0.000012)
        assert "0.000012" in result

        # Zero
        assert sender._format_price(0) == "N/A"

        # None
        assert sender._format_price(None) == "N/A"

        print("  All price formats correct")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 6: Percentage calculations ----
    print("--- TEST 6: Percentage calculations ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        # Target above entry (LONG)
        pct = sender._calc_pct(100, 105, "LONG")
        assert "+5.00%" == pct

        # Target below entry (SHORT)
        pct = sender._calc_pct(100, 95, "SHORT")
        assert "-5.00%" == pct

        # Stop loss
        sl = sender._calc_sl_pct(100, 97, "LONG")
        assert "-3.00%" == sl

        # Zero entry
        pct = sender._calc_pct(0, 100, "LONG")
        assert pct == "N/A"

        print("  Percentage calculations correct")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 7: Confidence bar ----
    print("--- TEST 7: Confidence bar ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        bar_100 = sender._make_conf_bar(100)
        assert bar_100 == "██████████"

        bar_50 = sender._make_conf_bar(50)
        assert bar_50 == "█████░░░░░"

        bar_0 = sender._make_conf_bar(0)
        assert bar_0 == "░░░░░░░░░░"

        bar_78 = sender._make_conf_bar(78)
        assert bar_78 == "███████░░░"

        print("  100%: {}".format(bar_100))
        print("   78%: {}".format(bar_78))
        print("   50%: {}".format(bar_50))
        print("    0%: {}".format(bar_0))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 8: Daily counter ----
    print("--- TEST 8: Daily counter ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        assert sender.get_public_count_today() == 0
        assert sender.get_public_remaining() == 2

        sender._public_count = 1
        assert sender.get_public_remaining() == 1

        sender._public_count = 2
        assert sender.get_public_remaining() == 0

        print("  Counter: 0→1→2, remaining: 2→1→0")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 9: Daily reset ----
    print("--- TEST 9: Daily counter reset ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        sender._public_count = 2
        sender._public_date = date.today() - timedelta(days=1)

        sender._check_daily_reset()

        assert sender._public_count == 0
        assert sender._public_date == date.today()

        print("  Counter reset on new day")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 10: Signal queue (sync parts) ----
    print("--- TEST 10: Signal queue ---")
    try:
        import asyncio
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        async def test_queue():
            s1 = make_sample_signal("BTC/USDT", "LONG", 70)
            s2 = make_sample_signal("ETH/USDT", "SHORT", 85)
            s3 = make_sample_signal("SOL/USDT", "LONG", 78)

            r1 = await sender.queue_signal(s1)
            r2 = await sender.queue_signal(s2)
            r3 = await sender.queue_signal(s3)

            assert r1 is True
            assert r2 is True
            assert r3 is True
            assert len(sender._signal_queue) == 3

            # Should be sorted: 85, 78, 70
            q = list(sender._signal_queue)
            assert q[0]["confidence"] == 85
            assert q[1]["confidence"] == 78
            assert q[2]["confidence"] == 70

            return True

        result = asyncio.get_event_loop().run_until_complete(
            test_queue()
        )

        assert result is True
        print("  Queue sorted by confidence: 85, 78, 70")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 11: Duplicate signal prevention ----
    print("--- TEST 11: Duplicate signal prevention ---")
    try:
        import asyncio
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        async def test_dup():
            s1 = make_sample_signal("BTC/USDT", "LONG", 70)
            s2 = make_sample_signal("BTC/USDT", "LONG", 80)

            r1 = await sender.queue_signal(s1)
            r2 = await sender.queue_signal(s2)

            assert r1 is True
            assert r2 is False
            assert len(sender._signal_queue) == 1

            return True

        result = asyncio.get_event_loop().run_until_complete(
            test_dup()
        )

        assert result is True
        print("  Duplicate BTC/USDT LONG rejected")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 12: Brain analysis formatting ----
    print("--- TEST 12: Brain analysis section ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        brains = {
            "RSI": {"direction": "LONG", "confidence": 80},
            "MACD": {"direction": "SHORT", "confidence": 60},
            "OBV": {"direction": "NEUTRAL", "confidence": 0},
        }

        section = sender._format_brain_analysis(brains)

        assert "RSI" in section
        assert "MACD" in section
        assert "OBV" in section
        assert "LONG" in section
        assert "SHORT" in section
        assert "80" in section

        print("  Brain section generated")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 13: Empty brain details ----
    print("--- TEST 13: Empty brain details ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        section = sender._format_brain_analysis({})
        assert "not available" in section.lower()

        section_none = sender._format_brain_analysis(None)
        assert "not available" in section_none.lower()

        print("  Handles empty/None brain details")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 14: Agreement emoji ----
    print("--- TEST 14: Agreement emoji ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        assert sender._agreement_emoji("STRONG") == "💪"
        assert sender._agreement_emoji("MODERATE") == "👍"
        assert sender._agreement_emoji("WEAK") == "👌"
        assert sender._agreement_emoji("MIXED") == "⚠️"
        assert sender._agreement_emoji("UNKNOWN") == "📊"

        print("  All agreement emojis correct")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 15: Fallback format ----
    print("--- TEST 15: Fallback signal format ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        msg = sender._format_fallback_signal({
            "pair": "BTC/USDT",
            "direction": "LONG",
            "confidence": 78,
            "entry_price": 67500,
        })

        assert "BTC/USDT" in msg
        assert "LONG" in msg
        assert len(msg) > 20

        # Completely empty signal
        msg2 = sender._format_fallback_signal({})
        assert len(msg2) > 10

        print("  Fallback format works")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 16: Stats ----
    print("--- TEST 16: Statistics ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        stats = sender.get_stats()

        assert "total_sent" in stats
        assert "total_failed" in stats
        assert "public_today" in stats
        assert "public_remaining" in stats
        assert "queue_size" in stats
        assert "is_sending" in stats
        assert "blocked_users" in stats

        assert stats["total_sent"] == 0
        assert stats["public_remaining"] == 2
        assert stats["queue_size"] == 0

        print("  Stats: {}".format(stats))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 17: History ----
    print("--- TEST 17: Send history ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        history = sender.get_history()
        assert isinstance(history, list)
        assert len(history) == 0

        sender._send_history.append({
            "pair": "BTC", "timestamp": "now"
        })
        assert len(sender.get_history()) == 1

        print("  History tracking works")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 18: Blocked users tracking ----
    print("--- TEST 18: Blocked user tracking ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        assert len(sender._blocked_users) == 0

        sender._blocked_users.add(11111)
        sender._blocked_users.add(22222)

        assert 11111 in sender._blocked_users
        assert 22222 in sender._blocked_users
        assert 33333 not in sender._blocked_users
        assert len(sender._blocked_users) == 2

        print("  Blocked user set working")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 19: Set bot instance ----
    print("--- TEST 19: Set bot instance ---")
    try:
        from bot.signal_sender import SignalSender
        sender = SignalSender()

        assert sender.bot is None

        class FakeBot:
            pass

        fake = FakeBot()
        sender.set_bot(fake)
        assert sender.bot is fake

        print("  Bot instance set correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 20: Singleton import ----
    print("--- TEST 20: Module singleton ---")
    try:
        from bot.signal_sender import signal_sender

        assert signal_sender is not None
        assert hasattr(signal_sender, 'distribute_signal')
        assert hasattr(signal_sender, 'send_to_public_channel')
        assert hasattr(signal_sender, 'send_to_private_users')
        assert hasattr(signal_sender, 'queue_signal')
        assert hasattr(signal_sender, 'process_queue')
        assert hasattr(signal_sender, 'send_custom_message')
        assert hasattr(signal_sender, 'broadcast_to_all')
        assert hasattr(signal_sender, 'format_signal_message')
        assert hasattr(signal_sender, 'get_stats')

        print("  Singleton accessible with all methods")
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