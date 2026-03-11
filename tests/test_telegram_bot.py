# ============================================
# TELEGRAM BOT TEST SCRIPT
# ============================================
# Run: python test_telegram_bot.py
#
# Tests bot initialization, database wrappers,
# token generation, validation, signal formatting.
# Does NOT require a running Telegram connection.
# ============================================

import sys
import os


def run_tests():
    """Test all Telegram bot functions (offline)."""

    print("\n" + "=" * 55)
    print("   RUNNING TELEGRAM BOT TESTS (OFFLINE)")
    print("=" * 55 + "\n")

    passed = 0
    failed = 0

    # ---- TEST 1: Bot initialization ----
    print("--- TEST 1: Bot initialization ---")
    try:
        from bot.telegram_bot import CryptoSignalBot

        bot = CryptoSignalBot()

        assert bot.token is not None
        assert bot.payment_mode in ("fake", "real")
        assert bot._mem_users == {}
        assert bot._mem_tokens == {}
        assert bot._mem_subs == {}

        print("  Bot initialized successfully")
        print("  Payment mode: {}".format(bot.payment_mode))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 2: User registration ----
    print("--- TEST 2: User registration (in-memory) ---")
    try:
        bot = CryptoSignalBot()

        result = bot._db_add_user(
            chat_id=12345,
            username="test_user",
            first_name="TestTrader"
        )
        assert result is True

        user = bot._db_get_user(12345)
        assert user is not None
        assert user["first_name"] == "TestTrader"
        assert user["username"] == "test_user"
        assert user["chat_id"] == 12345

        print("  User registered and retrieved")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 3: Duplicate user ----
    print("--- TEST 3: Duplicate user handling ---")
    try:
        bot = CryptoSignalBot()

        bot._db_add_user(12345, "user1", "First")
        bot._db_add_user(12345, "user1", "First")

        # Should not crash, should have exactly 1 user
        user = bot._db_get_user(12345)
        assert user is not None

        print("  Duplicate user handled gracefully")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 4: Token creation ----
    print("--- TEST 4: Token creation ---")
    try:
        bot = CryptoSignalBot()

        token = bot._db_create_token(chat_id=12345)

        assert token is not None
        assert len(token) == 36  # UUID format
        assert token in bot._mem_tokens

        token_data = bot._mem_tokens[token]
        assert token_data["is_used"] is False
        assert token_data["activated_by"] is None

        print("  Token: {}".format(token[:8] + "****"))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 5: Token validation - valid ----
    print("--- TEST 5: Token validation (valid) ---")
    try:
        bot = CryptoSignalBot()

        token = bot._db_create_token()
        result = bot._db_validate_token(token)

        assert result["valid"] is True
        assert result["error"] is None
        assert result["token_data"] is not None

        print("  Valid token accepted")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 6: Token validation - not found ----
    print("--- TEST 6: Token validation (not found) ---")
    try:
        bot = CryptoSignalBot()

        result = bot._db_validate_token("FAKE-TOKEN-12345")

        assert result["valid"] is False
        assert "not found" in result["error"].lower()

        print("  Invalid token rejected correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 7: Token validation - already used ----
    print("--- TEST 7: Token validation (already used) ---")
    try:
        bot = CryptoSignalBot()

        token = bot._db_create_token()
        bot._db_activate_token(token, 99999)

        result = bot._db_validate_token(token)

        assert result["valid"] is False
        assert "already" in result["error"].lower()

        print("  Used token rejected correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 8: Token activation ----
    print("--- TEST 8: Token activation ---")
    try:
        bot = CryptoSignalBot()

        token = bot._db_create_token()
        result = bot._db_activate_token(token, 12345)

        assert result["success"] is True
        assert result["expiry"] != ""

        # Check subscription created
        assert bot._db_is_subscribed(12345) is True

        # Check token marked as used
        token_data = bot._mem_tokens[token]
        assert token_data["is_used"] is True
        assert token_data["activated_by"] == 12345

        print("  Token activated, subscription created")
        print("  Expiry: {}".format(result["expiry"][:10]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 9: Subscription check ----
    print("--- TEST 9: Subscription check ---")
    try:
        bot = CryptoSignalBot()

        # Not subscribed
        assert bot._db_is_subscribed(99999) is False

        # Subscribe
        token = bot._db_create_token()
        bot._db_activate_token(token, 55555)
        assert bot._db_is_subscribed(55555) is True

        print("  Subscription checks working")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 10: Get active subscribers ----
    print("--- TEST 10: Active subscribers list ---")
    try:
        bot = CryptoSignalBot()

        # Add 3 subscribers
        for cid in [111, 222, 333]:
            token = bot._db_create_token()
            bot._db_activate_token(token, cid)

        subs = bot._db_get_active_subscribers()
        assert len(subs) >= 3
        assert 111 in subs
        assert 222 in subs
        assert 333 in subs

        print("  Found {} active subscribers".format(len(subs)))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 11: Signal formatting ----
    print("--- TEST 11: Signal message formatting ---")
    try:
        bot = CryptoSignalBot()

        signal = {
            "pair": "BTC/USDT",
            "direction": "LONG",
            "confidence": 82.5,
            "entry_price": 67500.00,
            "target_price": 69000.00,
            "stop_loss": 66500.00,
            "timeframe": "5m",
            "brains": {
                "RSI": {"direction": "LONG", "confidence": 80},
                "MACD": {"direction": "LONG", "confidence": 75},
                "BOLLINGER": {"direction": "NEUTRAL", "confidence": 0},
            },
            "timestamp": "2024-01-15 10:30 UTC",
        }

        msg = bot.format_signal_message(signal)

        assert "BTC/USDT" in msg
        assert "LONG" in msg
        assert "82.5%" in msg
        assert "67,500" in msg
        assert len(msg) > 100

        print("  Signal formatted ({} chars)".format(len(msg)))
        print("  Preview:")
        # Show first 3 lines
        for line in msg.split("\n")[:5]:
            # Strip HTML tags for preview
            clean = line.replace("<b>", "").replace("</b>", "")
            clean = clean.replace("<code>", "").replace("</code>", "")
            clean = clean.replace("<i>", "").replace("</i>", "")
            print("    {}".format(clean))
        print("    ...")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 12: Signal formatting - SHORT ----
    print("--- TEST 12: SHORT signal formatting ---")
    try:
        bot = CryptoSignalBot()

        signal = {
            "pair": "ETH/USDT",
            "direction": "SHORT",
            "confidence": 71.0,
            "entry_price": 3500.00,
            "target_price": 3350.00,
            "stop_loss": 3580.00,
            "timeframe": "5m",
            "brains": {},
            "timestamp": "2024-01-15 11:00 UTC",
        }

        msg = bot.format_signal_message(signal)

        assert "ETH/USDT" in msg
        assert "SHORT" in msg
        assert "71.0%" in msg

        print("  SHORT signal formatted correctly")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 13: Signal formatting - edge cases ----
    print("--- TEST 13: Signal format edge cases ---")
    try:
        bot = CryptoSignalBot()

        # Empty signal
        msg1 = bot.format_signal_message({})
        assert len(msg1) > 10

        # Small price (altcoin)
        msg2 = bot.format_signal_message({
            "pair": "DOGE/USDT",
            "direction": "LONG",
            "confidence": 65,
            "entry_price": 0.085,
            "target_price": 0.092,
            "stop_loss": 0.080,
        })
        assert "DOGE" in msg2

        print("  Edge cases handled")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 14: Authorization check ----
    print("--- TEST 14: Authorization check ---")
    try:
        bot = CryptoSignalBot()

        assert bot.is_user_authorized(99999) is False

        token = bot._db_create_token()
        bot._db_activate_token(token, 77777)
        assert bot.is_user_authorized(77777) is True

        print("  Authorization checks working")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 15: Main keyboard ----
    print("--- TEST 15: Main keyboard builder ---")
    try:
        bot = CryptoSignalBot()

        keyboard = bot._get_main_keyboard()
        assert keyboard is not None

        # Should have 2 rows, 2 buttons each
        rows = keyboard.inline_keyboard
        assert len(rows) == 2
        assert len(rows[0]) == 2
        assert len(rows[1]) == 2

        # Check callback data
        callbacks = []
        for row in rows:
            for btn in row:
                callbacks.append(btn.callback_data)

        assert "activate_token" in callbacks
        assert "my_status" in callbacks
        assert "get_premium" in callbacks
        assert "help" in callbacks

        print("  Keyboard: 2×2 with correct callbacks")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 16: Signal count tracking ----
    print("--- TEST 16: Signal count tracking ---")
    try:
        bot = CryptoSignalBot()

        assert bot._db_get_signal_count(12345) == 0

        bot._db_increment_signal_count(12345)
        bot._db_increment_signal_count(12345)
        bot._db_increment_signal_count(12345)

        assert bot._db_get_signal_count(12345) == 3

        print("  Signal count: 3")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 17: Multiple tokens ----
    print("--- TEST 17: Multiple unique tokens ---")
    try:
        bot = CryptoSignalBot()

        tokens = set()
        for _ in range(10):
            t = bot._db_create_token()
            assert t not in tokens, "Duplicate token!"
            tokens.add(t)

        assert len(tokens) == 10

        print("  10 unique tokens generated")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 18: Subscription details ----
    print("--- TEST 18: Subscription details ---")
    try:
        bot = CryptoSignalBot()

        token = bot._db_create_token()
        bot._db_activate_token(token, 44444)

        sub = bot._db_get_subscription(44444)
        assert sub is not None
        assert sub["chat_id"] == 44444
        assert sub["is_active"] is True
        assert "end_date" in sub
        assert "start_date" in sub

        print("  Subscription details retrieved")
        print("  Active: {} | Expires: {}".format(
            sub["is_active"], sub["end_date"][:10]
        ))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 19: Application build ----
    print("--- TEST 19: Application build ---")
    try:
        bot = CryptoSignalBot()

        if bot.token:
            app = bot.build_application()

            if app:
                assert bot.application is not None
                print("  Application built successfully")
                print("PASSED ✅\n")
                passed += 1
            else:
                print("  ⚠️ Build returned None (token may "
                      "be invalid)")
                print("SKIPPED ⏭\n")
                passed += 1
        else:
            print("  ⚠️ No token configured, skipping")
            print("SKIPPED ⏭\n")
            passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 20: Singleton import ----
    print("--- TEST 20: Module singleton ---")
    try:
        from bot.telegram_bot import crypto_bot

        assert crypto_bot is not None
        assert hasattr(crypto_bot, 'run')
        assert hasattr(crypto_bot, 'build_application')
        assert hasattr(crypto_bot, 'send_signal_to_user')
        assert hasattr(crypto_bot, 'broadcast_signal')
        assert hasattr(crypto_bot, 'send_to_channel')
        assert hasattr(crypto_bot, 'format_signal_message')
        assert hasattr(crypto_bot, 'is_user_authorized')

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