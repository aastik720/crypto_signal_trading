PROMPT FOR PHASE 1:
====================

Project: CryptoSignal Bot
Task: Create the complete project folder structure and configuration file.

Create this EXACT folder structure:

crypto_signal_bot/
│
├── config/
│   ├── __init__.py
│   └── settings.py
│
├── data/
│   ├── __init__.py
│   └── fetcher.py (empty placeholder)
│
├── algorithms/
│   ├── __init__.py
│   ├── rsi.py (empty placeholder)
│   ├── macd.py (empty placeholder)
│   ├── bollinger.py (empty placeholder)
│   ├── volume.py (empty placeholder)
│   └── signal_engine.py (empty placeholder)
│
├── bot/
│   ├── __init__.py
│   ├── telegram_bot.py (empty placeholder)
│   └── signal_sender.py (empty placeholder)
│
├── payments/
│   ├── __init__.py
│   └── razorpay_handler.py (empty placeholder)
│
├── database/
│   ├── __init__.py
│   └── db_manager.py (empty placeholder)
│
├── security/
│   ├── __init__.py
│   └── auth.py (empty placeholder)
│
├── notifications/
│   ├── __init__.py
│   └── reminders.py (empty placeholder)
│
├── utils/
│   ├── __init__.py
│   └── logger.py (empty placeholder)
│
├── .env
├── main.py (empty placeholder)
└── requirements.txt

NOW BUILD config/settings.py with these details:

The .env file must have these variables:
- TELEGRAM_BOT_TOKEN = ""
- TELEGRAM_PUBLIC_CHANNEL_ID = ""
- RAZORPAY_KEY_ID = ""
- RAZORPAY_KEY_SECRET = ""
- PAYMENT_MODE = "fake"  
  (THIS IS THE TOGGLE: "fake" = use random generated tokens 
   for testing, "real" = connect to Razorpay for actual payments)
- SUBSCRIPTION_PRICE = 999
- SUBSCRIPTION_DAYS = 28
- PUBLIC_CHANNEL_DAILY_LIMIT = 2
- SIGNAL_INTERVAL_MINUTES = 10
- MIN_CONFIDENCE_SCORE = 65
- DATABASE_PATH = "database/crypto_bot.db"
- LOG_FILE_PATH = "utils/bot_logs.log"

The settings.py must:
1. Load all .env variables using python-dotenv
2. Have a class called Config that holds all settings
3. Have constants for trading pairs list:
   TRADING_PAIRS = [
     "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", 
     "XRPUSDT", "ADAUSDT", "DOGEUSDT", "DOTUSDT",
     "MATICUSDT", "LINKUSDT"
   ]
4. Have timeframe constants:
   TIMEFRAME = "5m" (5 minute candles)
   RSI_PERIOD = 14
   MACD_FAST = 12
   MACD_SLOW = 26
   MACD_SIGNAL = 9
   BOLLINGER_PERIOD = 20
   BOLLINGER_STD = 2
   VOLUME_MA_PERIOD = 20
5. Print confirmation that config loaded successfully

requirements.txt must include:
python-telegram-bot==20.7
python-dotenv==1.0.0
websockets==12.0
aiohttp==3.9.1
pandas==2.1.4
numpy==1.26.2
ta==0.11.0
razorpay==1.4.1
aiosqlite==0.19.0
apscheduler==3.10.4
requests==2.31.0

Make everything production-ready.
Every file must have proper error handling.
Add comments explaining every section.