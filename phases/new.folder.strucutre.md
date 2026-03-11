crypto_signal_bot/
│
├── config/
│   └── settings.py
│
├── data/
│   └── fetcher.py
│
├── algorithms/
│   ├── ema_crossover.py      ← Brain 1 (TREND)
│   ├── vwap.py               ← Brain 2 (SMART MONEY)
│   ├── rsi.py                ← Brain 3 (MOMENTUM)
│   ├── stochastic_rsi.py     ← Brain 4 (EARLY MOMENTUM)
│   ├── bollinger.py          ← Brain 5 (VOLATILITY)
│   ├── obv.py                ← Brain 6 (VOLUME TRUTH)
│   ├── volume_profile.py     ← Brain 7 (VOLUME ZONES)
│   └── signal_engine.py      ← MASTER BRAIN
│
├── bot/
│   ├── telegram_bot.py
│   └── signal_sender.py
│
├── payments/
│   └── razorpay.py
│
├── database/
│   └── db_manager.py
│
├── security/
│   └── auth.py
│
├── notifications/
│   └── reminders.py
│
├── utils/
│   └── logger.py
│
└── main.py