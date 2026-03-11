PROMPT FOR PHASE 12:
====================

Project: CryptoSignal Bot (continuing from Phase 1-11)
Task: Build reminder system in notifications/reminders.py

CONTEXT: Users need reminders before subscription expires.
This module runs scheduled checks and sends reminders.

REMINDER SCHEDULE:
- Day 25 (3 days before expiry): First warning
- Day 27 (1 day before expiry): Urgent warning
- Day 28 (expiry day): Expired message
- After expiry: Daily reminder for 3 days, then stop

BUILD notifications/reminders.py with these EXACT specs:

CLASS: ReminderManager

FUNCTIONS:

1. __init__(self, bot_instance)
   - Initialize with telegram bot
   - Initialize database manager

2. async check_expiring_subscriptions(self)
   - Called every 6 hours by scheduler
   - Query database for users expiring in 1, 3 days
   - Send appropriate reminder to each
   - Mark reminder as sent (avoid duplicate reminders)

3. async send_3_day_warning(self, chat_id, expiry_date)
   - Message:
   """
   ⚠️ Subscription Expiring Soon!
   
   ⏳ Your premium access expires in 3 days
   📅 Expiry date: {expiry_date}
   
   Renew now to keep receiving signals!
   💰 ₹999 for 28 more days
   
   [🔄 Renew Now]
   """

4. async send_1_day_warning(self, chat_id, expiry_date)
   - Message:
   """
   🚨 URGENT: Subscription Expires Tomorrow!
   
   ⏳ Less than 24 hours remaining!
   📅 Expiry: {expiry_date}
   
   Don't miss out on profitable signals!
   💰 Renew for just ₹999
   
   [🔄 Renew Now] [📊 My Stats]
   """

5. async send_expired_message(self, chat_id)
   - Message:
   """
   ❌ Subscription Expired
   
   Your premium access has ended.
   You will no longer receive trading signals.
   
   📊 Your stats:
   • Signals received: {count}
   • Days active: 28
   
   Renew anytime to resume:
   💰 ₹999 for 28 days
   
   [🔄 Renew Now]
   """

6. async send_post_expiry_reminder(self, chat_id, days_since)
   - Sent on day 1, 2, 3 after expiry
   - Softer reminder to come back
   - After day 3, stop sending

7. async process_all_reminders(self)
   - Main function called by scheduler
   - Check all users
   - Send appropriate reminders
   - Handle errors per-user (don't stop if one fails)

Add database columns tracking:
- last_reminder_sent (to avoid duplicates)
- reminder_count (how many reminders sent)

Full working code. Production-ready.