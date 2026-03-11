# ============================================
# DATABASE TEST SCRIPT
# ============================================
# Run: python test_database.py
# Tests all 20 database functions.
# ============================================

import asyncio
from datetime import datetime, timedelta


async def run_tests():
    """Test all database operations."""

    # Import the singleton
    from database.db_manager import db

    print("\n" + "=" * 55)
    print("   RUNNING DATABASE TESTS")
    print("=" * 55 + "\n")

    # ---- TEST 1: Create Tables ----
    print("--- TEST 1: create_tables ---")
    result = await db.create_tables()
    assert result is True, "Table creation failed!"
    print("PASSED ✅\n")

    # ---- TEST 2: Add User ----
    print("--- TEST 2: add_user ---")
    result = await db.add_user("111111", "testuser", "TestName")
    assert result is True, "Add user failed!"
    print("PASSED ✅\n")

    # ---- TEST 3: Get User ----
    print("--- TEST 3: get_user ---")
    user = await db.get_user("111111")
    assert user is not None, "User not found!"
    assert user["chat_id"] == "111111"
    assert user["username"] == "testuser"
    assert user["is_active"] == 0
    print("User data: {}".format(user["first_name"]))
    print("PASSED ✅\n")

    # ---- TEST 4: Get All Users ----
    print("--- TEST 4: get_all_users ---")
    await db.add_user("222222", "user2", "User2")
    all_users = await db.get_all_users()
    assert len(all_users) >= 2, "Should have at least 2 users!"
    print("PASSED ✅\n")

    # ---- TEST 5: Update Subscription ----
    print("--- TEST 5: update_user_subscription ---")
    expiry = (datetime.now() + timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S")
    result = await db.update_user_subscription(
        "111111", "TOKEN_ABC_123", "FAKE_PAY_001", expiry
    )
    assert result is True
    user = await db.get_user("111111")
    assert user["is_active"] == 1
    assert user["token"] == "TOKEN_ABC_123"
    print("PASSED ✅\n")

    # ---- TEST 6: Is User Active ----
    print("--- TEST 6: is_user_active ---")
    active = await db.is_user_active("111111")
    assert active is True, "User should be active!"
    inactive = await db.is_user_active("222222")
    assert inactive is False, "User2 should be inactive!"
    nonexist = await db.is_user_active("999999")
    assert nonexist is False, "Non-existent user should be inactive!"
    print("PASSED ✅\n")

    # ---- TEST 7: Get All Active Users ----
    print("--- TEST 7: get_all_active_users ---")
    active_users = await db.get_all_active_users()
    assert len(active_users) >= 1
    print("PASSED ✅\n")

    # ---- TEST 8: Validate Token ----
    print("--- TEST 8: validate_token ---")
    valid = await db.validate_token("TOKEN_ABC_123", "111111")
    assert valid is True, "Token should be valid for owner!"
    stolen = await db.validate_token("TOKEN_ABC_123", "999999")
    assert stolen is False, "Token should fail for wrong chat_id!"
    fake = await db.validate_token("FAKE_TOKEN_XYZ", "111111")
    assert fake is False, "Non-existent token should fail!"
    print("PASSED ✅\n")

    # ---- TEST 9: Lock Token ----
    print("--- TEST 9: lock_token_to_chat ---")
    result = await db.lock_token_to_chat("TOKEN_ABC_123", "111111")
    assert result is True
    print("PASSED ✅\n")

    # ---- TEST 10: Token Info ----
    print("--- TEST 10: get_token_info ---")
    info = await db.get_token_info("TOKEN_ABC_123")
    assert info is not None
    assert info["locked_chat_id"] == "111111"
    print("PASSED ✅\n")

    # ---- TEST 11: Is Token Expired ----
    print("--- TEST 11: is_token_expired ---")
    expired = await db.is_token_expired("TOKEN_ABC_123")
    assert expired is False, "Token should not be expired yet!"
    expired_fake = await db.is_token_expired("NONEXISTENT")
    assert expired_fake is True, "Non-existent token should be expired!"
    print("PASSED ✅\n")

    # ---- TEST 12: Save Token ----
    print("--- TEST 12: save_token ---")
    new_expiry = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
    result = await db.save_token("222222", "TOKEN_USER2", new_expiry)
    assert result is True
    print("PASSED ✅\n")

    # ---- TEST 13: Increment Signal Count ----
    print("--- TEST 13: increment_signal_count ---")
    result = await db.increment_signal_count("111111")
    assert result is True
    user = await db.get_user("111111")
    assert user["total_signals_received"] == 1
    print("PASSED ✅\n")

    # ---- TEST 14: Log Signal ----
    print("--- TEST 14: log_signal ---")
    signal_id = await db.log_signal(
        pair="BTCUSDT",
        direction="LONG",
        entry_price=42500.50,
        target_1=43000.00,
        target_2=43500.00,
        stop_loss=42000.00,
        confidence=78.5,
        sent_public=True,
        sent_private=True
    )
    assert signal_id is not None
    assert signal_id > 0
    print("Signal ID: {}".format(signal_id))
    print("PASSED ✅\n")

    # ---- TEST 15: Public Channel Count ----
    print("--- TEST 15: get_today_public_count ---")
    count = await db.get_today_public_count()
    assert count == 0, "Should be 0 before increment!"
    print("PASSED ✅\n")

    # ---- TEST 16: Increment Public Count ----
    print("--- TEST 16: increment_public_count ---")
    result = await db.increment_public_count()
    assert result is True
    count = await db.get_today_public_count()
    assert count == 1
    print("PASSED ✅\n")

    # ---- TEST 17: Can Send Public ----
    print("--- TEST 17: can_send_public ---")
    can_send = await db.can_send_public()
    assert can_send is True, "Should be able to send (1 < 2 limit)!"
    # Send another
    await db.increment_public_count()
    can_send = await db.can_send_public()
    assert can_send is False, "Should NOT be able to send (2 >= 2 limit)!"
    print("PASSED ✅\n")

    # ---- TEST 18: Deactivate User ----
    print("--- TEST 18: deactivate_user ---")
    result = await db.deactivate_user("111111")
    assert result is True
    active = await db.is_user_active("111111")
    assert active is False
    print("PASSED ✅\n")

    # ---- TEST 19: Get Expiring Users ----
    print("--- TEST 19: get_expiring_users ---")
    # Reactivate user with 2-day expiry for testing
    short_expiry = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    await db.update_user_subscription("111111", "TOKEN_SHORT", "FAKE_002", short_expiry)
    expiring = await db.get_expiring_users(3)
    assert len(expiring) >= 1, "Should find at least 1 expiring user!"
    print("PASSED ✅\n")

    # ---- TEST 20: Signal Stats ----
    print("--- TEST 20: get_signal_stats ---")
    stats = await db.get_signal_stats()
    assert stats["total_signals"] >= 1
    assert stats["pending"] >= 1
    print("Stats: {}".format(stats))
    print("PASSED ✅\n")

    # ---- FINAL SUMMARY ----
    print("=" * 55)
    print("   ALL 20 TESTS PASSED ✅✅✅")
    print("=" * 55)

    # Clean up test database
    import os
    if os.path.exists(db.db_path):
        os.remove(db.db_path)
        print("\n[CLEANUP] Test database deleted")


# Run the tests
if __name__ == "__main__":
    asyncio.run(run_tests())