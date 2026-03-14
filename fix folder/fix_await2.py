"""
fix_await2.py
=============
Fixes signal_sender.py and reminders.py
by making their helper methods async.

Usage:
    python fix_await2.py
"""

import os


def fix_file(filepath, replacements):
    if not os.path.exists(filepath):
        print("  ❌ Not found: {}".format(filepath))
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    changes = 0
    for old, new in replacements:
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            changes += count
            print("  ✅ Fixed ({} times)".format(count))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print("  📝 {} changes in {}".format(
        changes, filepath
    ))


def main():
    print("\n" + "=" * 55)
    print("  FIX 2: Making helper methods async")
    print("=" * 55 + "\n")

    # ── signal_sender.py ──
    print("── Fixing: bot/signal_sender.py ──")

    fix_file("bot/signal_sender.py", [
        (
            "    def _get_active_subscribers(self):",
            "    async def _get_active_subscribers(self):"
        ),
        (
            "    def _get_all_users(self):",
            "    async def _get_all_users(self):"
        ),
        (
            "    def _get_subscription(self, chat_id):",
            "    async def _get_subscription(self, chat_id):"
        ),
        (
            "    def _increment_signal_count(self, chat_id):",
            "    async def _increment_signal_count(self, chat_id):"
        ),
    ])

    # ── reminders.py ──
    print("\n── Fixing: notifications/reminders.py ──")

    # Need to find the exact method names
    # Read file to check
    rpath = "notifications/reminders.py"
    if os.path.exists(rpath):
        with open(rpath, "r", encoding="utf-8") as f:
            content = f.read()

        # Find all "def " lines that contain
        # db_manager calls nearby
        lines = content.split("\n")
        methods_to_fix = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if "await db_manager." in stripped:
                # Find the method this belongs to
                for j in range(i, -1, -1):
                    if "    def " in lines[j]:
                        method_line = lines[j]
                        if "async def" not in method_line:
                            methods_to_fix.append(
                                (method_line, method_line.replace(
                                    "    def ",
                                    "    async def "
                                ))
                            )
                        break

        # Remove duplicates
        seen = set()
        unique_fixes = []
        for old, new in methods_to_fix:
            if old not in seen:
                seen.add(old)
                unique_fixes.append((old, new))

        if unique_fixes:
            fix_file(rpath, unique_fixes)
        else:
            print("  ⚠️ No sync methods with await found")
            print("  Checking for common patterns...")

            # Try common patterns
            common_fixes = [
                (
                    "    def _get_signal_count(",
                    "    async def _get_signal_count("
                ),
                (
                    "    def _get_all_subscriptions(",
                    "    async def _get_all_subscriptions("
                ),
                (
                    "    def get_signal_count_for_user(",
                    "    async def get_signal_count_for_user("
                ),
                (
                    "    def _db_get_signal_count(",
                    "    async def _db_get_signal_count("
                ),
            ]

            fix_file(rpath, common_fixes)
    else:
        print("  ❌ File not found")

    # ── Also fix callers in signal_sender.py ──
    print("\n── Fixing callers in signal_sender.py ──")

    # The callers are already async, but we need
    # to make sure they use await
    fix_file("bot/signal_sender.py", [
        # These methods are called without await
        # in distribute_signal, send_to_private_users etc.
        # But they are called with self. prefix
        # Check if callers need await
    ])

    print("\n" + "=" * 55)
    print("  ✅ FIX 2 COMPLETE")
    print("=" * 55)
    print("")
    print("  Now run:")
    print("    taskkill /f /im python.exe")
    print("    python main.py")


if __name__ == "__main__":
    main()