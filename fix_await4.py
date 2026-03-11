# Save as fix_await4.py

import os

def fix(filepath):
    if not os.path.exists(filepath):
        return
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Fix broken patterns
    fixes = [
        # signal_sender.await X() → await signal_sender.X()
        ("signal_sender.await ", "await signal_sender."),
        ("crypto_bot.await ", "await crypto_bot."),
        ("db_manager.await ", "await db_manager."),
        ("auth_manager.await ", "await auth_manager."),
        ("reminder_manager.await ", "await reminder_manager."),
        ("payment_manager.await ", "await payment_manager."),
        # self.await X() → await self.X()
        ("self.await ", "await self."),
        # double await
        ("await await ", "await "),
    ]
    
    changes = 0
    for old, new in fixes:
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            changes += count
            print("  Fixed '{}' → '{}' ({} times)".format(
                old, new, count
            ))
    
    if changes > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("  {} fixes in {}".format(changes, filepath))
    else:
        print("  ✅ {} OK".format(filepath))

print("\nFixing broken await patterns...\n")

fix("main.py")
fix("bot/telegram_bot.py")
fix("bot/signal_sender.py")
fix("notifications/reminders.py")
fix("security/auth.py")
fix("payments/razorpay.py")

print("\nDone! Run: python main.py")