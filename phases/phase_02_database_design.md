PROMPT FOR PHASE 2:
====================

Project: CryptoSignal Bot (continuing from Phase 1)
Task: Build the complete database system in database/db_manager.py

CONTEXT: This is a Telegram crypto signal bot. Users pay ₹999 
for 28 days access. Each user gets a unique token locked to 
their Telegram Chat ID. We use SQLite database.

The config/settings.py is already built (from Phase 1) with 
Config class that has DATABASE_PATH, SUBSCRIPTION_DAYS etc.

BUILD database/db_manager.py with these EXACT specifications:

DATABASE TABLES NEEDED:

TABLE 1: users
Columns:
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- chat_id (TEXT UNIQUE NOT NULL) - Telegram chat ID
- username (TEXT) - Telegram username
- first_name (TEXT) - User's first name
- join_date (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
- is_active (BOOLEAN DEFAULT 0) - subscription active or not
- token (TEXT UNIQUE) - their unique access token
- token_activated_date (TIMESTAMP) - when token was activated
- token_expiry_date (TIMESTAMP) - when token expires
- locked_chat_id (TEXT) - the chat ID this token is locked to
- total_signals_received (INTEGER DEFAULT 0)
- last_signal_time (TIMESTAMP)
- payment_id (TEXT) - Razorpay payment ID or "FAKE_TOKEN"
- created_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
- updated_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)

TABLE 2: signals_log
Columns:
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- pair (TEXT NOT NULL) - like "BTCUSDT"
- direction (TEXT NOT NULL) - "LONG" or "SHORT"
- entry_price (REAL NOT NULL)
- target_1 (REAL)
- target_2 (REAL)
- stop_loss (REAL)
- confidence (REAL NOT NULL) - confidence percentage
- signal_time (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
- was_sent_public (BOOLEAN DEFAULT 0)
- was_sent_private (BOOLEAN DEFAULT 0)
- result (TEXT) - "WIN", "LOSS", "PENDING"
- pnl_percent (REAL) - profit/loss percentage

TABLE 3: public_channel_tracker
Columns:
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- date (DATE NOT NULL) - today's date
- signals_sent_count (INTEGER DEFAULT 0) - count per day
- last_signal_time (TIMESTAMP)

FUNCTIONS NEEDED (all must be async):

User Management:
1. create_tables() - creates all 3 tables if not exist
2. add_user(chat_id, username, first_name) - adds new user
3. get_user(chat_id) - returns user data
4. get_all_active_users() - returns all users where is_active=1
5. get_all_users() - returns all users
6. update_user_subscription(chat_id, token, payment_id, 
   expiry_date) - activates subscription
7. deactivate_user(chat_id) - sets is_active=0
8. is_user_active(chat_id) - returns True/False
9. increment_signal_count(chat_id) - adds 1 to 
   total_signals_received

Token Management:
10. save_token(chat_id, token, expiry_date) - saves token
11. get_token_info(token) - returns token details
12. validate_token(token, chat_id) - checks if token is valid 
    AND belongs to this chat_id
13. lock_token_to_chat(token, chat_id) - locks token to 
    specific chat ID permanently
14. is_token_expired(token) - checks if 28 days passed
15. get_expiring_users(days_left) - returns users whose 
    subscription expires in X days

Signal Logging:
16. log_signal(pair, direction, entry, target1, target2, 
    stoploss, confidence, sent_public, sent_private)
17. get_today_public_count() - how many signals sent to 
    public channel today
18. increment_public_count() - adds 1 to today's count
19. can_send_public() - returns True if count < 2 for today
20. get_signal_stats() - returns total signals, win rate, 
    loss rate

Use aiosqlite for async database operations.
Import Config from config.settings.
Every function must have try-except error handling.
Every function must have docstring explaining what it does.
Print/log database operations for debugging.
Initialize database and create tables on import.
Make it production-ready and crash-proof.