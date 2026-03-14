"""
CryptoSignal Bot - Configuration
═════════════════════════════════
All settings loaded from .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    # ═══════════════════════════════════
    #  TELEGRAM BOT
    # ═══════════════════════════════════

    TELEGRAM_BOT_TOKEN = os.getenv(
        "TELEGRAM_BOT_TOKEN", ""
    )

    # ═══════════════════════════════════
    #  PUBLIC CHANNEL
    # ═══════════════════════════════════

    TELEGRAM_PUBLIC_CHANNEL_ID = os.getenv(
        "TELEGRAM_PUBLIC_CHANNEL_ID", ""
    )

    # ═══════════════════════════════════
    #  ADMIN
    # ═══════════════════════════════════

    _admin_raw = os.getenv("ADMIN_CHAT_IDS", "")
    ADMIN_IDS = [
        int(x.strip()) for x in _admin_raw.split(",")
        if x.strip().isdigit()
    ]

    # ═══════════════════════════════════
    #  SUBSCRIPTION
    # ═══════════════════════════════════

    SUBSCRIPTION_PRICE = int(
        os.getenv("SUBSCRIPTION_PRICE", "999")
    )
    SUBSCRIPTION_DAYS = int(
        os.getenv("SUBSCRIPTION_DAYS", "28")
    )

    # ═══════════════════════════════════
    #  PAYMENT MODE
    # ═══════════════════════════════════

    PAYMENT_MODE = os.getenv(
        "PAYMENT_MODE", "fake"
    ).lower()

    USE_RAZORPAY = (PAYMENT_MODE == "real")

    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv(
        "RAZORPAY_KEY_SECRET", ""
    )

    # ═══════════════════════════════════
    #  PRIVATE CHANNEL (not used)
    # ═══════════════════════════════════

    PRIVATE_CHANNEL_LINK = ""

    # ═══════════════════════════════════
    #  SIGNAL SETTINGS
    # ═══════════════════════════════════

    PUBLIC_CHANNEL_DAILY_LIMIT = int(
        os.getenv("PUBLIC_CHANNEL_DAILY_LIMIT", "2")
    )
    SIGNAL_INTERVAL_MINUTES = int(
        os.getenv("SIGNAL_INTERVAL_MINUTES", "25")
    )
    MIN_CONFIDENCE_SCORE = int(
        os.getenv("MIN_CONFIDENCE_SCORE", "65")
    )
    MIN_CONFIDENCE = MIN_CONFIDENCE_SCORE

    # ═══════════════════════════════════
    #  TIMEFRAME & TRADING
    # ═══════════════════════════════════

    TIMEFRAME = os.getenv("TIMEFRAME", "5m")
    
    CANDLE_LIMIT = int(os.getenv("CANDLE_LIMIT", "250"))

    # ═══════════════════════════════════
    #  STOCHASTIC RSI BRAIN
    # ═══════════════════════════════════

    STOCHRSI_K_PERIOD = int(
        os.getenv("STOCHRSI_K_PERIOD", "3")
    )
    STOCHRSI_D_PERIOD = int(
        os.getenv("STOCHRSI_D_PERIOD", "3")
    )
    STOCHRSI_PERIOD = int(
        os.getenv("STOCHRSI_PERIOD", "14")
    )

    TRADING_PAIRS = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
        "XRP/USDT",
        "ADA/USDT",
        "AVAX/USDT",
        "DOGE/USDT",
        "DOT/USDT",
        "MATIC/USDT",
    ]

    # ═══════════════════════════════════
    #  RSI BRAIN
    #  rsi.py reads: Config.RSI_PERIOD
    # ═══════════════════════════════════

    RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))

    # ═══════════════════════════════════
    #  MACD BRAIN
    #  macd.py reads: Config.MACD_FAST
    #                 Config.MACD_SLOW
    #                 Config.MACD_SIGNAL
    # ═══════════════════════════════════

    MACD_FAST = int(os.getenv("MACD_FAST", "12"))
    MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
    MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))

    # ═══════════════════════════════════
    #  BOLLINGER BRAIN
    #  bollinger.py reads: Config.BOLLINGER_PERIOD
    #                      Config.BOLLINGER_STD
    # ═══════════════════════════════════

    BOLLINGER_PERIOD = int(
        os.getenv("BOLLINGER_PERIOD", "20")
    )
    BOLLINGER_STD = float(
        os.getenv("BOLLINGER_STD", "2.0")
    )

    # ═══════════════════════════════════
    #  VOLUME BRAIN
    #  volume.py reads: Config.VOLUME_MA_PERIOD
    # ═══════════════════════════════════

    VOLUME_MA_PERIOD = int(
        os.getenv("VOLUME_MA_PERIOD", "20")
    )

    # ═══════════════════════════════════
    #  EMA / S&R / CANDLE / OBV
    #  These brains don't read from Config
    #  They use hardcoded defaults internally
    # ═══════════════════════════════════

    # ═══════════════════════════════════
    #  DATABASE
    # ═══════════════════════════════════

    DATABASE_PATH = os.getenv(
        "DATABASE_PATH", "database/crypto_bot.db"
    )

    # ═══════════════════════════════════
    #  LOGGING
    # ═══════════════════════════════════

    LOG_FILE_PATH = os.getenv(
        "LOG_FILE_PATH", "utils/bot_logs.log"
    )


# ═══════════════════════════════════════
#  STARTUP VERIFICATION
# ═══════════════════════════════════════

print("[CONFIG] ✅ Configuration loaded")
print("[CONFIG]    Bot Token: {}".format(
    "SET" if Config.TELEGRAM_BOT_TOKEN else "MISSING ❌"
))
print("[CONFIG]    Channel: {}".format(
    Config.TELEGRAM_PUBLIC_CHANNEL_ID or "NOT SET ⚠️"
))
print("[CONFIG]    Admins: {}".format(
    Config.ADMIN_IDS if Config.ADMIN_IDS else "NONE ⚠️"
))
print("[CONFIG]    Subscription: ₹{} / {} days".format(
    Config.SUBSCRIPTION_PRICE, Config.SUBSCRIPTION_DAYS
))
print("[CONFIG]    Payment: {}".format(
    Config.PAYMENT_MODE.upper()
))
print("[CONFIG]    Timeframe: {}".format(
    Config.TIMEFRAME
))
print("[CONFIG]    Signal interval: {} min".format(
    Config.SIGNAL_INTERVAL_MINUTES
))
print("[CONFIG]    Daily limit: {} public signals".format(
    Config.PUBLIC_CHANNEL_DAILY_LIMIT
))
print("[CONFIG]    Min confidence: {}%".format(
    Config.MIN_CONFIDENCE_SCORE
))
print("[CONFIG]    Pairs: {}".format(
    len(Config.TRADING_PAIRS)
))
print("[CONFIG]    Database: {}".format(
    Config.DATABASE_PATH
))