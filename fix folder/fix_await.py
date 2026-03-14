"""
fix_await.py
============
Automatically adds async/await to all database
calls across telegram_bot.py, signal_sender.py,
and reminders.py.

Creates backup of each file before modifying.

Usage:
    python fix_await.py
"""

import os
import shutil


def fix_file(filepath, replacements, description):
    """
    Apply text replacements to a file.
    Creates .backup before modifying.
    """
    if not os.path.exists(filepath):
        print("  ❌ File not found: {}".format(filepath))
        return False

    # Read original
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Backup
    backup = filepath + ".backup"
    shutil.copy2(filepath, backup)
    print("  📁 Backup: {}".format(backup))

    # Apply replacements
    changes = 0
    for old, new in replacements:
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            changes += count
            print("  ✅ '{}' → '{}' ({} times)".format(
                old[:50], new[:50], count
            ))

    if changes == 0:
        print("  ⚠️ No changes needed")
        return True

    # Write modified
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print("  📝 {} changes applied to {}".format(
        changes, filepath
    ))
    return True


def main():
    print("\n" + "=" * 55)
    print("  AUTO-FIX: Adding async/await to all files")
    print("=" * 55 + "\n")

    # ============================================
    # FILE 1: bot/telegram_bot.py
    # ============================================
    print("─" * 55)
    print("  Fixing: bot/telegram_bot.py")
    print("─" * 55)

    bot_replacements = [
        # ── Step A: Make _db methods async ──
        (
            "    def _db_add_user(self,",
            "    async def _db_add_user(self,"
        ),
        (
            "    def _db_get_user(self,",
            "    async def _db_get_user(self,"
        ),
        (
            "    def _db_create_token(self,",
            "    async def _db_create_token(self,"
        ),
        (
            "    def _db_validate_token(self,",
            "    async def _db_validate_token(self,"
        ),
        (
            "    def _db_activate_token(self,",
            "    async def _db_activate_token(self,"
        ),
        (
            "    def _db_is_subscribed(self,",
            "    async def _db_is_subscribed(self,"
        ),
        (
            "    def _db_get_subscription(self,",
            "    async def _db_get_subscription(self,"
        ),
        (
            "    def _db_get_signal_count(self,",
            "    async def _db_get_signal_count(self,"
        ),
        (
            "    def _db_get_active_subscribers(self)",
            "    async def _db_get_active_subscribers(self)"
        ),
        (
            "    def _db_increment_signal_count(self,",
            "    async def _db_increment_signal_count(self,"
        ),
        (
            "    def is_user_authorized(self,",
            "    async def is_user_authorized(self,"
        ),

        # ── Step B: Add await to db_manager calls ──
        # (inside the _db wrapper methods)
        # Make sure we don't double-await
        (
            "                    db_manager.add_user(",
            "                    await db_manager.add_user("
        ),
        (
            "                    db_manager.get_user(",
            "                    await db_manager.get_user("
        ),
        (
            "                    db_manager.create_token(",
            "                    await db_manager.create_token("
        ),
        (
            "                        db_manager.create_token(",
            "                        await db_manager.create_token("
        ),
        (
            "                    db_manager.get_token(",
            "                    await db_manager.get_token("
        ),
        (
            "                    token_data = db_manager.get_token(",
            "                    token_data = await db_manager.get_token("
        ),
        (
            "                    db_manager.activate_token(",
            "                    await db_manager.activate_token("
        ),
        (
            "                    result = db_manager.is_subscribed(",
            "                    result = await db_manager.is_subscribed("
        ),
        (
            "                    sub = db_manager.get_subscription(",
            "                    sub = await db_manager.get_subscription("
        ),
        (
            "                    count = db_manager.get_signal_count(",
            "                    count = await db_manager.get_signal_count("
        ),
        (
            "                    db_subs = db_manager.get_active_subscribers(",
            "                    db_subs = await db_manager.get_active_subscribers("
        ),
        (
            "                    db_manager.increment_signal_count(",
            "                    await db_manager.increment_signal_count("
        ),

        # ── Step C: Add await to self._db calls ──
        # These are called from async handlers
        (
            "            self._db_add_user(",
            "            await self._db_add_user("
        ),
        (
            "            is_active = self._db_is_subscribed(",
            "            is_active = await self._db_is_subscribed("
        ),
        (
            "            sub = self._db_get_subscription(",
            "            sub = await self._db_get_subscription("
        ),
        (
            "            signal_count = self._db_get_signal_count(",
            "            signal_count = await self._db_get_signal_count("
        ),
        (
            "            user_data = self._db_get_user(",
            "            user_data = await self._db_get_user("
        ),
        (
            "                token_str = self._db_create_token(",
            "                token_str = await self._db_create_token("
        ),
        (
            "            validation = self._db_validate_token(",
            "            validation = await self._db_validate_token("
        ),
        (
            "            result = self._db_activate_token(",
            "            result = await self._db_activate_token("
        ),
        (
            "        return self._db_is_subscribed(",
            "        return await self._db_is_subscribed("
        ),
        (
            "            self._db_increment_signal_count(",
            "            await self._db_increment_signal_count("
        ),
        (
            "            subscribers = self._db_get_active_subscribers(",
            "            subscribers = await self._db_get_active_subscribers("
        ),
        (
            "                    self._db_increment_signal_count(",
            "                    await self._db_increment_signal_count("
        ),
    ]

    fix_file(
        "bot/telegram_bot.py",
        bot_replacements,
        "Telegram Bot"
    )

    # ============================================
    # FILE 2: bot/signal_sender.py
    # ============================================
    print("\n" + "─" * 55)
    print("  Fixing: bot/signal_sender.py")
    print("─" * 55)

    sender_replacements = [
        # db_manager calls inside async methods
        (
            "                    subs = db_manager.get_active_subscribers(",
            "                    subs = await db_manager.get_active_subscribers("
        ),
        (
            "                    users = db_manager.get_all_users(",
            "                    users = await db_manager.get_all_users("
        ),
        (
            "                    sub = db_manager.get_subscription(",
            "                    sub = await db_manager.get_subscription("
        ),
        (
            "                    db_manager.increment_signal_count(",
            "                    await db_manager.increment_signal_count("
        ),
    ]

    fix_file(
        "bot/signal_sender.py",
        sender_replacements,
        "Signal Sender"
    )

    # ============================================
    # FILE 3: notifications/reminders.py
    # ============================================
    print("\n" + "─" * 55)
    print("  Fixing: notifications/reminders.py")
    print("─" * 55)

    reminder_replacements = [
        (
            "                    count = db_manager.get_signal_count(",
            "                    count = await db_manager.get_signal_count("
        ),
        (
            "                    db_subs = db_manager.get_all_subscriptions(",
            "                    db_subs = await db_manager.get_all_subscriptions("
        ),
    ]

    fix_file(
        "notifications/reminders.py",
        reminder_replacements,
        "Reminders"
    )

    # ============================================
    # DONE
    # ============================================
    print("\n" + "=" * 55)
    print("  ✅ ALL FIXES APPLIED")
    print("=" * 55)
    print("")
    print("  Backup files created with .backup extension")
    print("  If something breaks, rename .backup to .py")
    print("")
    print("  Now run:")
    print("    taskkill /f /im python.exe")
    print("    python main.py")
    print("")


if __name__ == "__main__":
    main()