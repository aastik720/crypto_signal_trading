PROMPT FOR PHASE 14:
====================

Project: CryptoSignal Bot (continuing from Phase 1-13)
Task: Build main.py - the entry point that connects everything

CONTEXT: main.py starts the bot and runs it 24/7. It connects:
- Telegram bot (user interface)
- Signal engine (analysis)
- Signal sender (distribution)
- Scheduler (periodic tasks)
- Database (data storage)
- Security (authentication)
- Reminders (notifications)
- Logger (logging)

ALL modules are now built. main.py must wire them together.

BUILD main.py with these EXACT specifications:

THE MAIN LOOP:
1. Initialize logger
2. Initialize database (create tables)
3. Initialize Binance data fetcher
4. Initialize Signal Engine
5. Initialize Telegram bot
6. Initialize Signal Sender
7. Initialize Auth Manager
8. Initialize Reminder Manager
9. Setup APScheduler for periodic tasks

SCHEDULED TASKS:

Task 1: Signal Scan (every 10 minutes)
- Run signal_engine.get_best_signal()
- If signal exists (confidence >= 65%):
  * Send via signal_sender.distribute_signal()
  * Log the signal
- If no signal: log "No qualifying signal this cycle"
- Runs 24/7, every 10 minutes

Task 2: Subscription Check (every 1 hour)
- Run auth_manager.check_and_expire()
- Deactivate expired users
- Runs every hour

Task 3: Reminder Check (every 6 hours)
- Run reminder_manager.process_all_reminders()
- Send warnings to expiring users
- Runs every 6 hours

Task 4: Data Refresh (every 5 minutes)
- Refresh cached data from Binance
- Keep data fresh for analysis

Task 5: Daily Reset (at midnight UTC)
- Reset public channel signal counter
- Generate daily performance report
- Log daily stats

STARTUP SEQUENCE:
```python
async def main():
    print("=" * 50)
    print("🤖 CryptoSignal Bot Starting...")
    print("=" * 50)
    
    # Step 1: Load config
    print("📋 Loading configuration...")
    config = Config()
    
    # Step 2: Setup logger
    print("📝 Setting up logger...")
    
    # Step 3: Initialize database
    print("🗄️ Initializing database...")
    db = DatabaseManager()
    await db.create_tables()
    
    # Step 4: Initialize data fetcher
    print("📡 Connecting to Binance...")
    fetcher = BinanceDataFetcher()
    
    # Step 5: Initialize signal engine
    print("🧠 Initializing 4 brains...")
    engine = SignalEngine()
    
    # Step 6: Initialize auth
    print("🔐 Setting up security...")
    auth = AuthManager()
    
    # Step 7: Payment mode check
    if config.PAYMENT_MODE == "fake":
        print("⚠️ FAKE TOKEN MODE - Testing only!")
    else:
        print("💰 REAL PAYMENT MODE - Razorpay active")
    
    # Step 8: Initialize Telegram bot
    print("🤖 Starting Telegram bot...")
    # Setup bot with all handlers
    
    # Step 9: Initialize scheduler
    print("⏰ Starting scheduler...")
    # Setup all scheduled tasks
    
    # Step 10: Start everything
    print("✅ Bot is LIVE and running!")
    print(f"📊 Monitoring {len(Config.TRADING_PAIRS)} pairs")
    print(f"⏱️ Signal scan every {Config.SIGNAL_INTERVAL} min")
    print(f"🎯 Min confidence: {Config.MIN_CONFIDENCE}%")
    print("=" * 50)
    
    # Run bot (blocks forever)
    await application.run_polling()