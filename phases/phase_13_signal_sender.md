PROMPT FOR PHASE 10:
====================

Project: CryptoSignal Bot (continuing from Phase 1-9)
Task: Build the signal sender in bot/signal_sender.py

CONTEXT: This module takes generated signals and sends them 
to two places:
1. PUBLIC CHANNEL: Maximum 2 signals per day (free preview)
2. PRIVATE (direct to subscribed users): Unlimited signals

The signal comes from SignalEngine in this format:
{
  "pair": "BTC/USDT",
  "direction": "LONG",
  "entry_price": 43250.00,
  "target_1": 44100.00,
  "target_2": 45500.00,
  "stop_loss": 42800.00,
  "confidence": 78,
  "valid_for_minutes": 10,
  "timestamp": datetime,
  "brain_details": {...},
  "agreement_level": "STRONG",
  "risk_reward": 2.5
}

ALREADY BUILT:
- database/db_manager.py → can check public channel count, 
  get active users, etc.
- config/settings.py → has PUBLIC_CHANNEL_DAILY_LIMIT, 
  TELEGRAM_PUBLIC_CHANNEL_ID

BUILD bot/signal_sender.py with these EXACT specifications:

CLASS: SignalSender

FUNCTIONS:

1. __init__(self, bot_instance)
   - Takes the telegram bot instance
   - Initialize database manager
   - Initialize signal counter

2. format_signal_message(self, signal, is_public=False)
   - Format signal into beautiful Telegram message
   - Use emojis and proper formatting
   
   FOR PRIVATE (full signal):
   """
   ⚡ SIGNAL ALERT
   
   🪙 Pair     : {pair}
   📈 Direction : {direction} (with 📈 for LONG, 📉 for SHORT)
   💰 Entry    : ${entry_price}
   🎯 Target 1 : ${target_1}
   🎯 Target 2 : ${target_2}
   🛑 Stop Loss: ${stop_loss}
   ⭐ Confidence: {confidence}%
   📊 Risk/Reward: {risk_reward}
   ⏰ Valid for : {valid_for} minutes
   
   🧠 Brain Analysis:
   • RSI: {rsi_direction} ({rsi_confidence}%)
   • MACD: {macd_direction} ({macd_confidence}%)
   • Bollinger: {boll_direction} ({boll_confidence}%)
   • Volume: {vol_direction} ({vol_confidence}%)
   or curently new added brian  i think aprox 8 brain so 
   
   Agreement: {agreement_level}
   
   ⏳ Next scan in 10 minutes
   """
   
   FOR PUBLIC (limited info to tease):
   """
   ⚡ FREE SIGNAL ALERT
   
   🪙 Pair     : {pair}
   📈 Direction : {direction}
   💰 Entry    : ${entry_price}
   🎯 Target 1 : ${target_1}
   🛑 Stop Loss: ${stop_loss}
   ⭐ Confidence: {confidence}%
   
   🔒 Get Target 2 + Brain Analysis 
   with Premium! ₹999/28 days
   
   📊 {public_count}/2 free signals today
   
   🤖 @YourBotUsername
   """

3. async send_to_public_channel(self, signal)
   - Check if daily limit reached (max 2)
   - If limit reached: skip
   - If allowed: format as public message and send to channel
   - Update public count in database
   - Log the signal
   - Return: True if sent, False if limit reached

4. async send_to_private_users(self, signal)
   - Get all active (subscribed) users from database
   - For each user:
     * Verify subscription is still active
     * Format as private (full) message
     * Send to their chat_id
     * Increment their signal count
     * Handle "bot blocked by user" error
     * Handle any send errors
   - Add 50ms delay between sends (avoid rate limiting)
   - Log total sent count

5. async distribute_signal(self, signal)
   - THIS IS THE MAIN FUNCTION called by the scheduler
   - First: try send to public channel
   - Then: send to all private users
   - Log everything
   - Return summary: {
       "signal": signal,
       "sent_public": True/False,
       "private_users_sent": count,
       "private_users_failed": count,
       "errors": [list of errors]
     }

6. async send_custom_message(self, chat_id, message)
   - Send any custom message to specific user
   - Used for reminders, alerts, etc.

7. async broadcast_to_all(self, message)
   - Send message to ALL users (active and inactive)
   - Used for announcements

SIGNAL QUEUE SYSTEM:
- If multiple signals generated at same time, queue them
- Send one every 30 seconds to avoid spam
- Priority: highest confidence first

IMPORTANT:
- Handle Telegram rate limits (max 30 messages/second)
- Handle blocked/deleted users gracefully
- Remove users who blocked the bot from active list
- Log every send attempt
- Never crash even if sending fails