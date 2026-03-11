# ============================================
# AUTH MANAGER TEST SCRIPT
# ============================================
# Run: python test_auth.py
#
# Tests token generation, validation, activation,
# anti-sharing, expiry, and audit logging.
# Does NOT require Telegram or database connection.
# ============================================

import asyncio
from datetime import datetime, timedelta


def run_async(coro):
    """Helper to run async functions in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def run_tests():
    """Test all AuthManager functions."""

    print("\n" + "=" * 55)
    print("   RUNNING AUTH MANAGER TESTS")
    print("=" * 55 + "\n")

    passed = 0
    failed = 0

    # ---- TEST 1: Initialization ----
    print("--- TEST 1: Initialization ---")
    try:
        from security.auth import AuthManager

        auth = AuthManager()

        assert auth._tokens == {}
        assert auth._subscriptions == {}
        assert auth._sharing_attempts == {}
        assert len(auth._flagged_users) == 0
        assert auth._sub_days == 28

        print("  AuthManager initialized")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 2: Token generation ----
    print("--- TEST 2: Token generation ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        token = auth.generate_token()

        assert token is not None
        assert token.startswith("CSB-")
        assert len(token) >= 30
        assert len(token) <= 45

        print("  Token: {}".format(token[:12] + "****"))
        print("  Length: {}".format(len(token)))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 3: Token uniqueness ----
    print("--- TEST 3: Token uniqueness ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        tokens = set()
        for _ in range(20):
            t = auth.generate_token()
            assert t not in tokens, "Duplicate token!"
            tokens.add(t)

        assert len(tokens) == 20

        print("  20 unique tokens generated")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 4: Token format ----
    print("--- TEST 4: Token format validation ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        token = auth.generate_token()

        # Check CSB- prefix
        assert token[:4] == "CSB-"

        # Check UUID format after prefix
        uuid_part = token[4:]
        parts = uuid_part.split("-")
        assert len(parts) == 5

        # Check uppercase
        assert token == token.upper()

        print("  Format: CSB-<UUID4> ✅")
        print("  Uppercase: ✅")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 5: Create subscription ----
    print("--- TEST 5: Create subscription ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            result = await auth.create_subscription(
                chat_id=12345,
                payment_id="TEST_PAY_001"
            )

            assert result["success"] is True
            assert result["token"] is not None
            assert result["token"].startswith("CSB-")
            assert result["expiry_date"] is not None
            assert result["chat_id"] == 12345

            # Verify subscription stored
            assert 12345 in auth._subscriptions
            sub = auth._subscriptions[12345]
            assert sub["is_active"] is True
            assert sub["payment_id"] == "TEST_PAY_001"

            return result

        result = run_async(test())

        print("  Token: {}****".format(result["token"][:12]))
        print("  Expiry: {}".format(result["expiry_date"][:10]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 6: Validate valid token ----
    print("--- TEST 6: Validate valid token ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            sub = await auth.create_subscription(11111)
            token = sub["token"]

            result = await auth.validate_token(token, 11111)

            assert result["status"] in ("VALID", "ALREADY_ACTIVE"), \
                "Expected VALID/ALREADY_ACTIVE, got {}".format(
                    result["status"]
                )

            return result

        result = run_async(test())

        print("  Status: {}".format(result["status"]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 7: Validate invalid token ----
    print("--- TEST 7: Validate invalid token ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            # Non-existent token
            result = await auth.validate_token(
                "CSB-FAKE-TOKEN-12345678-XXXX-YYYY", 11111
            )
            assert result["status"] == "INVALID_TOKEN"

            # Wrong format
            result2 = await auth.validate_token(
                "WRONG-FORMAT", 11111
            )
            assert result2["status"] == "INVALID_TOKEN"

            # Too short
            result3 = await auth.validate_token("CSB-123", 11111)
            assert result3["status"] == "INVALID_TOKEN"

            # Empty
            result4 = await auth.validate_token("", 11111)
            assert result4["status"] == "INVALID_TOKEN"

            return True

        result = run_async(test())

        print("  Non-existent: INVALID_TOKEN ✅")
        print("  Wrong format: INVALID_TOKEN ✅")
        print("  Too short: INVALID_TOKEN ✅")
        print("  Empty: INVALID_TOKEN ✅")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 8: Token locked to other user ----
    print("--- TEST 8: Token locked (SHARING ATTEMPT) ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            # User A creates subscription
            sub_a = await auth.create_subscription(11111)
            token = sub_a["token"]

            # User B tries to use same token
            result = await auth.validate_token(token, 22222)

            assert result["status"] == "LOCKED", \
                "Expected LOCKED, got {}".format(result["status"])

            # Check sharing attempt recorded
            assert auth.get_sharing_attempts(22222) == 1

            return result

        result = run_async(test())

        print("  Token locked to user A, user B rejected")
        print("  Status: {}".format(result["status"]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 9: Anti-sharing flagging ----
    print("--- TEST 9: Anti-sharing flagging ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            # Create 3 tokens for user A
            tokens = []
            for _ in range(3):
                sub = await auth.create_subscription(11111)
                tokens.append(sub["token"])

            # User B tries all 3 tokens (3 attempts)
            for t in tokens:
                await auth.validate_token(t, 22222)

            # User B should be flagged
            assert auth.is_user_flagged(22222), \
                "User should be flagged after 3 attempts"
            assert auth.get_sharing_attempts(22222) == 3

            return True

        result = run_async(test())

        print("  3 sharing attempts → user FLAGGED 🚩")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 10: Token activation ----
    print("--- TEST 10: Token activation ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            # Generate token manually
            token = auth.generate_token()

            # Store it (simulating purchase without activation)
            auth._tokens[token] = {
                "token": token,
                "chat_id": None,
                "created_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "activated_at": None,
                "expires_at": (
                    datetime.now() + timedelta(days=28)
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "is_active": False,
                "is_used": False,
                "payment_id": "TEST",
            }

            # Activate for user
            result = await auth.activate_token(token, 33333)

            assert result["success"] is True
            assert result["status"] == "ACTIVATED"
            assert result["expiry_date"] is not None

            # Verify locked
            assert auth._token_usage[token] == 33333
            assert auth._tokens[token]["is_used"] is True
            assert auth._tokens[token]["chat_id"] == 33333

            # Verify subscription created
            assert await auth.is_authorized(33333) is True

            return result

        result = run_async(test())

        print("  Token activated and locked to chat:33333")
        print("  Status: {}".format(result["status"]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 11: Authorization check ----
    print("--- TEST 11: is_authorized ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            # Not subscribed
            assert await auth.is_authorized(99999) is False

            # Create subscription
            await auth.create_subscription(44444)
            assert await auth.is_authorized(44444) is True

            return True

        result = run_async(test())

        print("  Unauthorized: False ✅")
        print("  Subscribed: True ✅")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 12: Expired token check ----
    print("--- TEST 12: Expired token validation ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            # Create token with past expiry
            token = auth.generate_token()

            auth._tokens[token] = {
                "token": token,
                "chat_id": None,
                "created_at": "2024-01-01 00:00:00",
                "activated_at": None,
                "expires_at": "2024-01-29 00:00:00",
                "is_active": False,
                "is_used": False,
                "payment_id": "EXPIRED_TEST",
            }

            result = await auth.validate_token(token, 55555)

            assert result["status"] == "EXPIRED", \
                "Expected EXPIRED, got {}".format(
                    result["status"]
                )

            return result

        result = run_async(test())

        print("  Expired token correctly rejected")
        print("  Status: {}".format(result["status"]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 13: Auto-expire check ----
    print("--- TEST 13: check_and_expire ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            # Create 2 subs: one expired, one active
            auth._subscriptions[11111] = {
                "chat_id": 11111,
                "token": "CSB-EXPIRED",
                "start_date": "2024-01-01 00:00:00",
                "end_date": "2024-01-29 00:00:00",
                "is_active": True,
                "payment_id": "TEST",
            }

            auth._subscriptions[22222] = {
                "chat_id": 22222,
                "token": "CSB-ACTIVE",
                "start_date": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "end_date": (
                    datetime.now() + timedelta(days=20)
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "is_active": True,
                "payment_id": "TEST",
            }

            expired = await auth.check_and_expire()

            assert 11111 in expired, \
                "11111 should be expired"
            assert 22222 not in expired, \
                "22222 should NOT be expired"

            # Verify deactivated
            assert auth._subscriptions[11111][
                "is_active"
            ] is False
            assert auth._subscriptions[22222][
                "is_active"
            ] is True

            return expired

        result = run_async(test())

        print("  Expired: {} user(s)".format(len(result)))
        print("  Active sub preserved ✅")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 14: Subscription info ----
    print("--- TEST 14: get_subscription_info ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            sub = await auth.create_subscription(66666)

            info = await auth.get_subscription_info(66666)

            assert info["has_subscription"] is True
            assert info["is_active"] is True
            assert info["days_remaining"] >= 27
            assert info["token_masked"] != "****"
            assert "CSB-" in info["token_masked"]
            assert info["is_flagged"] is False
            assert info["sharing_attempts"] == 0

            return info

        info = run_async(test())

        print("  Active: {}".format(info["is_active"]))
        print("  Days left: {}".format(info["days_remaining"]))
        print("  Token: {}".format(info["token_masked"]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 15: No subscription info ----
    print("--- TEST 15: No subscription info ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            info = await auth.get_subscription_info(99999)

            assert info["has_subscription"] is False
            assert info["is_active"] is False
            assert info["days_remaining"] == 0

            return info

        info = run_async(test())

        print("  No subscription: correct defaults")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 16: Revoke token ----
    print("--- TEST 16: Token revocation ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            sub = await auth.create_subscription(77777)
            token = sub["token"]

            assert await auth.is_authorized(77777) is True

            result = await auth.revoke_token(token)

            assert result["success"] is True
            assert result["affected_chat_id"] == 77777

            # Token should be deactivated
            assert auth._tokens[token]["is_active"] is False

            # Subscription should be deactivated
            assert auth._subscriptions[77777][
                "is_active"
            ] is False

            return result

        result = run_async(test())

        print("  Token revoked, subscription deactivated")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 17: Double activation (same user) ----
    print("--- TEST 17: Double activation (same user) ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            sub = await auth.create_subscription(88888)
            token = sub["token"]

            # Try activating again (same user)
            result = await auth.activate_token(token, 88888)

            assert result["success"] is True
            assert result["status"] == "ALREADY_ACTIVE"

            return result

        result = run_async(test())

        print("  Re-activation: ALREADY_ACTIVE ✅")
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 18: Audit log ----
    print("--- TEST 18: Audit log ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            await auth.create_subscription(11111)
            await auth.validate_token("CSB-FAKE-INVALID", 22222)

            log = auth.get_audit_log(limit=10)
            assert len(log) >= 2

            # Check log entry structure
            entry = log[0]
            assert "timestamp" in entry
            assert "event" in entry
            assert "success" in entry

            # Check filtering
            failures = auth.get_audit_log(
                event_type="TOKEN_REJECTED"
            )
            assert len(failures) >= 1

            return len(log)

        count = run_async(test())

        print("  Audit log entries: {}".format(count))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 19: Security stats ----
    print("--- TEST 19: Security stats ---")
    try:
        from security.auth import AuthManager
        auth = AuthManager()

        async def test():
            await auth.create_subscription(11111)
            await auth.create_subscription(22222)

            stats = auth.get_security_stats()

            assert "total_tokens" in stats
            assert "active_subscriptions" in stats
            assert "flagged_users" in stats
            assert stats["total_tokens"] >= 2
            assert stats["active_subscriptions"] >= 2

            return stats

        stats = run_async(test())

        print("  Tokens: {}".format(stats["total_tokens"]))
        print("  Active subs: {}".format(
            stats["active_subscriptions"]
        ))
        print("  Flagged: {}".format(stats["flagged_users"]))
        print("PASSED ✅\n")
        passed += 1
    except Exception as e:
        print("FAILED ❌ {}\n".format(e))
        failed += 1

    # ---- TEST 20: Singleton import ----
    print("--- TEST 20: Module singleton ---")
    try:
        from security.auth import auth_manager

        assert auth_manager is not None
        assert hasattr(auth_manager, 'generate_token')
        assert hasattr(auth_manager, 'create_subscription')
        assert hasattr(auth_manager, 'validate_token')
        assert hasattr(auth_manager, 'activate_token')
        assert hasattr(auth_manager, 'is_authorized')
        assert hasattr(auth_manager, 'check_and_expire')
        assert hasattr(auth_manager, 'get_subscription_info')
        assert hasattr(auth_manager, 'revoke_token')
        assert hasattr(auth_manager, 'is_user_flagged')
        assert hasattr(auth_manager, 'get_audit_log')
        assert hasattr(auth_manager, 'get_security_stats')

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