"""
fix_await3.py
=============
Finds ALL missing await calls across ALL files.
Fixes every coroutine that is called without await.

Usage:
    python fix_await3.py
"""

import os
import re


def scan_and_fix(filepath):
    """
    Scan file for calls to async methods
    that are missing await.
    """
    if not os.path.exists(filepath):
        print("  ❌ Not found: {}".format(filepath))
        return 0

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # List of async method names we know about
    async_methods = [
        "_db_add_user",
        "_db_get_user",
        "_db_create_token",
        "_db_validate_token",
        "_db_activate_token",
        "_db_is_subscribed",
        "_db_get_subscription",
        "_db_get_signal_count",
        "_db_get_active_subscribers",
        "_db_increment_signal_count",
        "_get_active_subscribers",
        "_get_all_users",
        "_get_subscription",
        "_increment_signal_count",
        "is_user_authorized",
        "db_manager.add_user",
        "db_manager.get_user",
        "db_manager.create_token",
        "db_manager.get_token",
        "db_manager.activate_token",
        "db_manager.is_subscribed",
        "db_manager.get_subscription",
        "db_manager.get_signal_count",
        "db_manager.get_active_subscribers",
        "db_manager.get_all_users",
        "db_manager.get_all_subscriptions",
        "db_manager.increment_signal_count",
        "db_manager.is_user_active",
        "db_manager.deactivate_user",
        "db_manager.save_token",
        "db_manager.get_token_info",
        "db_manager.validate_token",
        "db_manager.lock_token_to_chat",
        "db_manager.is_token_expired",
        "db_manager.get_expiring_users",
        "db_manager.deactivate_token",
        "db_manager.get_all_active_users",
    ]

    changes = 0
    new_lines = []

    for i, line in enumerate(lines):
        original = line
        stripped = line.strip()

        # Skip comments and empty lines
        if stripped.startswith("#") or stripped == "":
            new_lines.append(line)
            continue

        # Skip lines that already have await
        if "await" in line and any(
            m in line for m in async_methods
        ):
            new_lines.append(line)
            continue

        # Skip def lines (method definitions)
        if "def " in stripped and "(" in stripped:
            new_lines.append(line)
            continue

        # Skip except/try/if/elif/else
        if stripped.startswith(("except", "try:",
                                "finally:")):
            new_lines.append(line)
            continue

        # Check if any async method is called
        # without await
        modified = False
        for method in async_methods:
            # Check if method is called in this line
            if method + "(" in line:
                # Make sure await is not already there
                # Find the position of the method call
                pos = line.find(method + "(")
                before = line[:pos].rstrip()

                # Check if await already exists
                if "await " + method in line:
                    continue
                if "await self." + method in line:
                    continue

                # Check we are inside an async function
                # (we assume yes since handlers are async)

                # Add await before the method call
                # Handle different patterns:

                # Pattern: variable = self.method(
                # Pattern: variable = db_manager.method(
                # Pattern: self.method(
                # Pattern: db_manager.method(

                if "self." + method in line:
                    old_call = "self." + method + "("
                    new_call = "await self." + method + "("

                    # Don't double-await
                    if "await self." + method in line:
                        continue

                    line = line.replace(
                        old_call, new_call, 1
                    )
                    modified = True

                elif "db_manager." in method:
                    # method already includes db_manager.
                    old_call = method + "("
                    new_call = "await " + method + "("

                    if "await " + method in line:
                        continue

                    line = line.replace(
                        old_call, new_call, 1
                    )
                    modified = True

                elif method + "(" in line:
                    # Generic: find and add await
                    old_call = method + "("
                    new_call = "await " + method + "("

                    if "await " + method in line:
                        continue

                    line = line.replace(
                        old_call, new_call, 1
                    )
                    modified = True

        if modified:
            changes += 1
            print("  Line {}: FIXED".format(i + 1))
            print("    OLD: {}".format(
                original.rstrip()
            ))
            print("    NEW: {}".format(
                line.rstrip()
            ))

        new_lines.append(line)

    # Write back
    if changes > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    return changes


def main():
    print("\n" + "=" * 55)
    print("  FIX 3: Find ALL missing await calls")
    print("=" * 55 + "\n")

    files_to_fix = [
        "main.py",
        "bot/telegram_bot.py",
        "bot/signal_sender.py",
        "notifications/reminders.py",
        "security/auth.py",
        "payments/razorpay.py",
    ]

    total = 0

    for filepath in files_to_fix:
        print("─" * 55)
        print("  Scanning: {}".format(filepath))
        print("─" * 55)

        count = scan_and_fix(filepath)
        total += count

        if count == 0:
            print("  ✅ No missing awaits found")
        else:
            print("  📝 {} fixes applied".format(count))

        print("")

    print("=" * 55)
    print("  TOTAL: {} missing awaits fixed".format(total))
    print("=" * 55)
    print("")
    print("  Now run:")
    print("    taskkill /f /im python.exe")
    print("    python main.py")
    print("")


if __name__ == "__main__":
    main()