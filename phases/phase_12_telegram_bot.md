PROMPT FOR PHASE 9:
====================

Project: CryptoSignal Bot (continuing from Phase 1-8)
Task: Build the Telegram bot in bot/telegram_bot.py

CONTEXT: This is the user-facing interface. Users interact 
with this bot. The bot handles:
1. New user registration
2. Token activation (user enters their token to activate)
3. Subscription status check
4. Help and info commands

Token system has 2 modes (from .env PAYMENT_MODE):
- "fake" mode: Bot generates a random token when user clicks 
  "Get Token" (for testing)
- "real" mode: Bot shows Razorpay payment link, token only 
  generated after payment confirmed

ALREADY BUILT FILES:
- config/settings.py → Config class
- database/db_manager.py → DatabaseManager class
- security/auth.py → (will be built, for now assume it exists)

BUILD bot/telegram_bot.py with these EXACT specifications:

Use python-telegram-bot v20+ (async version)

BOT COMMANDS AND FLOW:

/start COMMAND:
- Check if user exists in database
- If new user: Add to database, show welcome message
- If existing user: Show their current status
- WELCOME MESSAGE:
  """
  🤖 Welcome to CryptoSignal Bot!
  
  📊 AI-powered crypto trading signals
  🎯 65%+ confidence signals only
  ⏰ Real-time analysis every 10 minutes
  
  💎 Premium Access: ₹999 for 28 days
  
  What you get:
  ✅ Unlimited trading signals
  ✅ All 10 major crypto pairs
  ✅ Entry, Target, Stop Loss
  ✅ AI confidence scoring
  ✅ 24/7 market monitoring
  
  Choose an option below 👇
  """
- Show InlineKeyboard buttons:
  [🔑 Activate Token] [📊 My Status]
  [💰 Get Premium] [ℹ️ Help]

/status COMMAND:
- Show user's subscription status
- If active: Show expiry date, signals received, days left
- If inactive: Show "No active subscription" + buy prompt
- FORMAT:
  """
  📊 Your Status
  
  👤 Name: {first_name}
  🆔 Chat ID: {chat_id}
  📅 Member since: {join_date}
  
  🔐 Subscription: ACTIVE ✅ / INACTIVE ❌
  📅 Expires: {expiry_date}
  ⏳ Days left: {days_remaining}
  📈 Signals received: {total_signals}
  🔑 Token: {last 4 chars}****
  """

/help COMMAND:
- Show all available commands and how the bot works
- Show FAQ

TOKEN ACTIVATION FLOW:
When user clicks "Activate Token":
1. Bot asks: "Please enter your activation token:"
2. Bot waits for user to type/paste token
3. Bot validates token:
   a. Does token exist in database?
   b. Is token already used by another chat ID? → REJECT
   c. Is token expired? → REJECT
   d. If valid: Lock token to this chat ID
4. On success:
   """
   ✅ Token Activated Successfully!
   
   🔐 Your access is now active
   📅 Valid until: {expiry_date}
   📈 Signals will start flowing!
   
   You will receive signals every 10 minutes
   for all qualifying pairs (65%+ confidence)
   """
5. On failure: Show specific error message

GET PREMIUM FLOW:
If PAYMENT_MODE == "fake":
  - Generate a random token (UUID format)
  - Save to database with 28 day expiry
  - Show token to user immediately
  - Message:
    """
    🎁 TEST MODE - Free Token Generated!
    
    🔑 Your Token: {token}
    
    Copy this token and click "Activate Token" 
    to start receiving signals.
    
    ⚠️ This is test mode. In production, 
    payment will be required.
    """

If PAYMENT_MODE == "real":
  - Generate Razorpay payment link (call payments module)
  - Show payment link to user
  - Message:
    """
    💰 Premium Subscription
    
    💎 Plan: 28 Days Access
    💰 Price: ₹999
    
    Click below to pay securely via Razorpay:
    🔗 {payment_link}
    
    After payment, your token will be sent 
    automatically. Then click "Activate Token" 
    to enter it.
    """

CONVERSATION HANDLER for token input:
- Use ConversationHandler from python-telegram-bot
- States: WAITING_FOR_TOKEN
- When user sends text after clicking "Activate Token":
  validate and process
- Timeout after 60 seconds

CALLBACK QUERY HANDLERS:
- Handle all InlineKeyboard button clicks
- "activate_token" → start token activation flow
- "my_status" → show status
- "get_premium" → show payment/fake token
- "help" → show help

ERROR HANDLING:
- Catch all exceptions
- Send user-friendly error messages
- Log all errors
- Never crash the bot

ADDITIONAL FUNCTIONS:

1. is_user_authorized(chat_id)
   - Quick check if user has active subscription
   - Return True/False

2. send_unauthorized_message(chat_id)
   - Send message that they need subscription
   - Include "Get Premium" button

FULL WORKING CODE with all imports, all handlers, 
Application builder setup. Ready to run.
Do NOT leave any placeholder or TODO.