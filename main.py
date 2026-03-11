# ============================================
# CRYPTO SIGNAL BOT - MAIN ENTRY POINT
# ============================================
# Master orchestrator that starts and runs
# the entire bot system.
#
# Startup sequence:
#   1. Load configuration
#   2. Initialize database
#   3. Initialize data fetcher
#   4. Initialize all algorithms & signal engine
#   5. Initialize payment system
#   6. Start Telegram Bot & Message Handlers
#   7. Start Background Workers
#   8. Run 24/7 Signal Generation Cycles
#
# Usage:
#   python main.py
#
# Stop:
#   Ctrl+C (graceful shutdown)
# ============================================

import asyncio
import signal
import sys
import os
import time
from datetime import datetime, timedelta

# ============================================
# STEP 0: Add project root to Python path
# ============================================

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ============================================
# STEP 1: Import all modules with safe loading
# ============================================

print("\n" + "=" * 55)
print("   CRYPTO SIGNAL BOT - STARTING UP")
print("=" * 55 + "\n")
print("[MAIN] Loading modules...\n")

# ────────────────────────────────────
#  CRITICAL MODULES
# ────────────────────────────────────

# Config
try:
    from config.settings import Config
    CONFIG_LOADED = True
    print("[MAIN] ✅ Config module loaded")
except Exception as e:
    print("[MAIN] ❌ FATAL: Config module failed: {}".format(e))
    CONFIG_LOADED = False

# Database
try:
    from database.db_manager import db
    DATABASE_LOADED = True
    print("[MAIN] ✅ Database module loaded")
except Exception as e:
    print("[MAIN] ❌ FATAL: Database module failed: {}".format(e))
    DATABASE_LOADED = False
    db = None

# Data Fetcher
try:
    from data.fetcher import fetcher
    FETCHER_LOADED = True
    print("[MAIN] ✅ Fetcher module loaded")
except Exception as e:
    print("[MAIN] ❌ FATAL: Fetcher module failed: {}".format(e))
    FETCHER_LOADED = False
    fetcher = None

# Logger
try:
    from utils.logger import bot_logger, performance_tracker
    LOGGER_LOADED = True
    print("[MAIN] ✅ Logger & Performance modules loaded")
except Exception as e:
    print("[MAIN] ❌ FATAL: Logger module failed: {}".format(e))
    LOGGER_LOADED = False
    bot_logger = None
    performance_tracker = None

# ────────────────────────────────────
#  ENGINES & BOT MODULES
# ────────────────────────────────────

# Signal Engine
try:
    from algorithms.signal_engine import signal_engine
    ENGINE_LOADED = True
    print("[MAIN] ✅ Signal Engine loaded")
except Exception as e:
    print("[MAIN] ❌ FATAL: Signal Engine failed: {}".format(e))
    ENGINE_LOADED = False
    signal_engine = None

# Telegram Bot & Sender
try:
    from bot.telegram_bot import crypto_bot
    from bot.signal_sender import signal_sender
    BOT_LOADED = True
    print("[MAIN] ✅ Telegram Bot & Sender loaded")
except Exception as e:
    print("[MAIN] ❌ FATAL: Bot modules failed: {}".format(e))
    BOT_LOADED = False
    crypto_bot = None
    signal_sender = None

# Security / Auth
try:
    from security.auth import auth_manager
    AUTH_LOADED = True
    print("[MAIN] ✅ Security/Auth module loaded")
except Exception as e:
    print("[MAIN] ❌ FATAL: Auth module failed: {}".format(e))
    AUTH_LOADED = False
    auth_manager = None

# Payment System
try:
    from payments.razorpay import payment_manager
    PAYMENT_LOADED = True
    print("[MAIN] ✅ Payment module loaded")
except Exception as e:
    print("[MAIN] ⚠️ Payment module failed: {}".format(e))
    PAYMENT_LOADED = False
    payment_manager = None

# Reminders
try:
    from notifications.reminders import reminder_manager
    REMINDERS_LOADED = True
    print("[MAIN] ✅ Reminder system loaded")
except Exception as e:
    print("[MAIN] ⚠️ Reminders module failed: {}".format(e))
    REMINDERS_LOADED = False
    reminder_manager = None

print("\n[MAIN] Module loading complete\n")


# ============================================
# HELPER: Safely resolve coroutines
# ============================================

async def safe_resolve(value):
    """
    If value is a coroutine, await it.
    Otherwise return as-is.

    This prevents 'coroutine has no len()' errors
    when an async function is accidentally called
    without await somewhere in a sub-module.

    Args:
        value: Any value or coroutine

    Returns:
        The resolved value (awaited if needed)
    """
    if asyncio.iscoroutine(value):
        return await value
    if asyncio.isfuture(value):
        return await value
    return value


# ============================================
# MAIN ORCHESTRATOR CLASS
# ============================================

class CryptoSignalBotMaster:
    """
    Main bot orchestrator.

    Controls the entire lifecycle:
    - Module health checks
    - Async initialization (DB, fetcher, Bot)
    - Starts background workers
    - Signal generation cycles
    - Graceful shutdown

    Connected modules:
    ┌─────────────────────────────────────────┐
    │  Config         → settings for all      │
    │  Database       → storage               │
    │  Fetcher        → Binance price data    │
    │  SignalEngine   → 8-brain analysis      │
    │  SignalSender   → distribute signals    │
    │  AuthManager    → tokens & security     │
    │  PaymentManager → Razorpay / fake mode  │
    │  TelegramBot    → user commands         │
    │  Reminders      → expiry warnings       │
    │  Logger         → logging & tracking    │
    └─────────────────────────────────────────┘
    """

    def __init__(self):
        self.is_running = False
        self.cycle_count = 0
        self.signals_generated = 0
        self.start_time = None
        self._ws_task = None
        self._workers = []
        self.app = None  # Telegram Application

        print("[MAIN] Bot orchestrator created")

    # ============================================
    # MODULE HEALTH CHECK
    # ============================================

    def check_modules(self):
        """
        Verifies all modules loaded successfully.

        Critical modules must ALL pass.
        Optional modules log warnings but don't block.

        Returns:
            bool: True if all critical modules loaded
        """
        print("\n[MAIN] ── Module Health Check ──\n")

        critical_ok = True

        # Critical — bot cannot run without these
        critical_modules = [
            ("Config", CONFIG_LOADED),
            ("Database", DATABASE_LOADED),
            ("Data Fetcher", FETCHER_LOADED),
            ("Logger", LOGGER_LOADED),
            ("Signal Engine", ENGINE_LOADED),
            ("Telegram Bot", BOT_LOADED),
            ("Security/Auth", AUTH_LOADED),
        ]

        for name, loaded in critical_modules:
            if loaded:
                print("[MAIN]   ✅ {:<18}: OK".format(name))
            else:
                print("[MAIN]   ❌ {:<18}: FAILED "
                      "(CRITICAL)".format(name))
                critical_ok = False

        # Optional — bot can run without these
        optional_modules = [
            ("Payment System", PAYMENT_LOADED),
            ("Reminders", REMINDERS_LOADED),
        ]

        for name, loaded in optional_modules:
            if loaded:
                print("[MAIN]   ✅ {:<18}: OK".format(name))
            else:
                print("[MAIN]   ⚠️  {:<18}: NOT LOADED "
                      "(optional)".format(name))

        if critical_ok:
            print("\n[MAIN] ── All critical checks "
                  "PASSED ──\n")
        else:
            print("\n[MAIN] ── Critical checks "
                  "FAILED ──\n")

        return critical_ok
    # ============================================
    # ASYNC INITIALIZATION
    # ============================================

    async def initialize(self):
        """
        Initialize all async components.

        Steps:
        1. Create database tables
        2. Test Binance API connection
        3. Build Telegram bot application
        4. Link all sub-systems together
        5. Display configuration summary

        Returns:
            bool: True if initialization succeeded
        """
        print("[MAIN] ── Initializing Components ──\n")

        # ────────────────────────────────
        # Step 1: Database
        # ────────────────────────────────
        print("[MAIN] Step 1/5: Creating database tables...")
        try:
            tables_ok = await db.create_tables()
            if tables_ok:
                print("[MAIN]   ✅ Database tables ready\n")
            else:
                print("[MAIN]   ⚠️ Database tables returned "
                      "False — continuing\n")
        except Exception as e:
            print("[MAIN]   ❌ Database init error: "
                  "{}\n".format(e))
            return False

        # ────────────────────────────────
        # Step 2: Binance API
        # ────────────────────────────────
        print("[MAIN] Step 2/5: Testing Binance API...")
        try:
            test_price = await fetcher.get_current_price(
                "BTCUSDT"
            )
            if test_price and test_price > 0:
                print("[MAIN]   ✅ Binance API OK | "
                      "BTC = ${:,.2f}\n".format(test_price))
            else:
                print("[MAIN]   ⚠️ Binance returned "
                      "no data\n")
        except Exception as e:
            print("[MAIN]   ⚠️ Binance test failed: "
                  "{}\n".format(e))

        # ────────────────────────────────
        # Step 3: Build Telegram Application
        # ────────────────────────────────
        print("[MAIN] Step 3/5: Building Telegram bot...")
        try:
            self.app = crypto_bot.build_application()
            print("[MAIN]   ✅ Telegram application built\n")
        except Exception as e:
            print("[MAIN]   ❌ Telegram build failed: "
                  "{}\n".format(e))
            return False

        # ────────────────────────────────
        # Step 4: Link all sub-systems
        # ────────────────────────────────
        print("[MAIN] Step 4/5: Linking sub-systems...")

        try:
            # Signal Sender needs bot to send messages
            signal_sender.set_bot(crypto_bot)
            print("[MAIN]   ✅ Signal Sender ← Bot linked")
        except Exception as e:
            print("[MAIN]   ❌ Sender link failed: "
                  "{}".format(e))
            return False

        # Reminders need bot to send warnings
        if REMINDERS_LOADED and reminder_manager:
            try:
                reminder_manager.set_bot(crypto_bot)
                print("[MAIN]   ✅ Reminders ← Bot linked")
            except Exception as e:
                print("[MAIN]   ⚠️ Reminders link failed: "
                      "{}".format(e))

        # Payment Manager — already initialized as singleton
        if PAYMENT_LOADED and payment_manager:
            print("[MAIN]   ✅ Payment Manager ready "
                  "({})".format(
                      "Razorpay" if Config.USE_RAZORPAY
                      else "Fake mode"
                  ))

        # Auth Manager — load existing subscriptions from DB
        if AUTH_LOADED and auth_manager:
            try:
                active_users = await db.get_all_active_users()
                loaded = 0

                for user in active_users:
                    chat_id = user.get("chat_id")
                    token = user.get("token")
                    expiry = user.get("token_expiry_date")

                    if chat_id and token and expiry:
                        auth_manager._tokens[token] = {
                            "token": token,
                            "chat_id": int(chat_id),
                            "created_at": user.get(
                                "token_activated_date", ""
                            ),
                            "activated_at": user.get(
                                "token_activated_date", ""
                            ),
                            "expires_at": expiry,
                            "is_active": True,
                            "is_used": True,
                            "payment_id": user.get(
                                "payment_id", ""
                            ),
                        }
                        auth_manager._token_usage[token] = (
                            int(chat_id)
                        )
                        auth_manager._subscriptions[
                            int(chat_id)
                        ] = {
                            "chat_id": int(chat_id),
                            "token": token,
                            "start_date": user.get(
                                "token_activated_date", ""
                            ),
                            "end_date": expiry,
                            "is_active": True,
                            "payment_id": user.get(
                                "payment_id", ""
                            ),
                        }
                        loaded += 1

                print("[MAIN]   ✅ Auth Manager ready | "
                      "Loaded {} subscription(s)".format(
                          loaded
                      ))
            except Exception as e:
                print("[MAIN]   ⚠️ Auth DB load failed: "
                      "{}".format(e))
                print("[MAIN]   ✅ Auth Manager ready "
                      "(memory only)")

        print("")

        # ────────────────────────────────
        # Step 5: Configuration summary
        # ────────────────────────────────
        print("[MAIN] Step 5/5: Configuration")
        print("[MAIN]   Payment Mode    : {}".format(
            Config.PAYMENT_MODE.upper()
        ))
        print("[MAIN]   Trading Pairs   : {} pairs".format(
            len(Config.TRADING_PAIRS)
        ))
        print("[MAIN]   Timeframe       : {}".format(
            Config.TIMEFRAME
        ))
        print("[MAIN]   Signal Interval : {} min".format(
            Config.SIGNAL_INTERVAL_MINUTES
        ))
        print("[MAIN]   Min Confidence  : {}%".format(
            Config.MIN_CONFIDENCE_SCORE
        ))
        print("[MAIN]   Subscription    : ₹{} / {} days".format(
            Config.SUBSCRIPTION_PRICE,
            Config.SUBSCRIPTION_DAYS
        ))
        print("[MAIN]   Public Channel  : {}".format(
            Config.TELEGRAM_PUBLIC_CHANNEL_ID or "(not set)"
        ))
        print("[MAIN]   Admins          : {}".format(
            Config.ADMIN_IDS or "(none)"
        ))
        print("")
        print("[MAIN] ── Initialization COMPLETE ──\n")

        if bot_logger:
            bot_logger.log_startup()

        return True

    # ============================================
    # BACKGROUND WORKERS
    # ============================================

    async def _reminder_worker(self):
        """
        Runs the reminder check every 6 hours.

        Sends expiry warnings to users whose
        subscription expires within 3 days.
        """
        print("[MAIN] ⏰ Reminder worker started "
              "(every 6 hours)")

        while self.is_running:
            try:
                if reminder_manager:
                    await reminder_manager.process_all_reminders()

                # Also send expiry warnings via signal sender
                if signal_sender:
                    try:
                        await signal_sender.send_expiry_warnings(
                            days_before=3
                        )
                    except Exception as e:
                        print("[WORKER] ⚠️ Expiry warning "
                              "error: {}".format(e))

            except Exception as e:
                if bot_logger:
                    bot_logger.log_error("WORKER.Reminders", e)
                else:
                    print("[WORKER] ❌ Reminder error: "
                          "{}".format(e))

            # Sleep 6 hours in small chunks
            for _ in range(6 * 3600):
                if not self.is_running:
                    break
                await asyncio.sleep(1)

    async def _auth_expiry_worker(self):
        """
        Runs the auth expiry check every hour.

        Finds and deactivates expired subscriptions.
        Sends expiry notification to affected users.
        """
        print("[MAIN] 🔒 Auth expiry worker started "
              "(every 1 hour)")

        while self.is_running:
            try:
                if auth_manager:
                    expired = await auth_manager.check_and_expire()

                    if expired:
                        print("[WORKER] ⏰ {} subscription(s) "
                              "expired".format(len(expired)))

                        if bot_logger:
                            bot_logger.info(
                                "Auto-expired {} users".format(
                                    len(expired)
                                ),
                                "AUTH",
                            )

                        # Notify expired users
                        if signal_sender:
                            for chat_id in expired:
                                try:
                                    msg = (
                                        "⏰ <b>Subscription "
                                        "Expired</b>\n\n"
                                        "Your premium access "
                                        "has ended.\n\n"
                                        "You will no longer "
                                        "receive trading "
                                        "signals.\n\n"
                                        "💎 Renew: ₹{}/{} days\n"
                                        "Use /subscribe to "
                                        "continue!"
                                    ).format(
                                        Config.SUBSCRIPTION_PRICE,
                                        Config.SUBSCRIPTION_DAYS,
                                    )
                                    await signal_sender \
                                        .send_custom_message(
                                            chat_id, msg
                                        )
                                    await asyncio.sleep(0.05)
                                except Exception:
                                    pass

            except Exception as e:
                if bot_logger:
                    bot_logger.log_error("WORKER.Auth", e)
                else:
                    print("[WORKER] ❌ Auth expiry error: "
                          "{}".format(e))

            # Sleep 1 hour in small chunks
            for _ in range(3600):
                if not self.is_running:
                    break
                await asyncio.sleep(1)

    # ============================================
    # SIGNAL GENERATION CYCLE (The 10-Min Loop)
    # ============================================

    async def run_signal_cycle(self):
        """
        Runs ONE complete signal generation cycle.

        Pipeline:
        1. SignalEngine scans all pairs, picks #1 best
        2. Log signal to database
        3. Distribute via SignalSender (public + private)
        4. Update database with send status
        5. If no signal → send "no trade" to subscribers
        """
        self.cycle_count += 1
        cycle_start = time.time()

        print("\n" + "─" * 55)
        print("  CYCLE #{} STARTING | {}".format(
            self.cycle_count,
            datetime.now().strftime("%H:%M:%S")
        ))
        print("─" * 55)

        try:
            # ── 1. Scan all pairs and pick best ──
            scan_result = await signal_engine.scan_and_pick_best()

            if (scan_result["has_signal"] and
                    scan_result["best_signal"]):

                best_sig = scan_result["best_signal"]

                # ── 2. Log signal to database ──
                sig_id = None
                try:
                    sig_id = await db.log_signal(
                        pair=best_sig["pair"],
                        direction=best_sig["direction"],
                        entry_price=best_sig["entry_price"],
                        target_1=best_sig["target_1"],
                        target_2=best_sig["target_2"],
                        stop_loss=best_sig["stop_loss"],
                        confidence=best_sig["confidence"],
                        sent_public=False,
                        sent_private=False,
                    )
                    best_sig["signal_id"] = sig_id
                except Exception as e:
                    print("[CYCLE] ⚠️ DB log error: "
                          "{}".format(e))

                # ── 3. Distribute signal ──
                dist_result = await signal_sender \
                    .distribute_signal(best_sig)

                # ── 4. Update DB with send status ──
                if sig_id:
                    try:
                        await db.update_signal_sent_status(
                            sig_id,
                            sent_public=dist_result[
                                "sent_public"
                            ],
                            sent_private=(
                                dist_result[
                                    "private_users_sent"
                                ] > 0
                            ),
                        )
                    except Exception as e:
                        print("[CYCLE] ⚠️ DB update error: "
                              "{}".format(e))

                self.signals_generated += 1

            else:
                # ── 5. No signal — send honest message ──
                no_trade_msg = scan_result.get(
                    "no_trade_message"
                )

                if no_trade_msg and signal_sender:
                    # FIX: await the async call and
                    # use safe_resolve as safety net
                    active_subs = await safe_resolve(
                        await signal_sender._get_active_subscribers()
                    )

                    # Ensure we got a list, not None
                    if not active_subs:
                        active_subs = []

                    if len(active_subs) > 0:
                        print("[MAIN] 📡 Sending 'No Trade' "
                              "to {} subscriber(s)".format(
                                  len(active_subs)
                              ))

                        for cid in active_subs:
                            try:
                                await signal_sender \
                                    .send_custom_message(
                                        cid, no_trade_msg
                                    )
                                await asyncio.sleep(0.05)
                            except Exception:
                                pass
                    else:
                        print("[CYCLE] ℹ️ No active "
                              "subscribers to notify")

        except Exception as e:
            print("[CYCLE] ❌ Critical cycle error: "
                  "{}".format(e))
            if bot_logger:
                bot_logger.log_error(
                    "MAIN.Cycle", e, tb_info=True
                )

        elapsed = time.time() - cycle_start

        print("\n" + "═" * 55)
        print("  CYCLE #{} COMPLETE | {:.1f}s".format(
            self.cycle_count, elapsed
        ))
        print("  Signals generated (all-time): {}".format(
            self.signals_generated
        ))
        print("═" * 55 + "\n")

    # ============================================
    # WEBSOCKET CALLBACK
    # ============================================

    async def on_candle_close(self, candle_data):
        """
        Callback when a WebSocket candle closes.

        Currently just logs. Can be extended to
        trigger real-time analysis.
        """
        symbol = candle_data.get("symbol", "UNKNOWN")
        close_price = candle_data.get("close", 0)
        print("[WS] 🕯️ Closed: {} | ${:,.2f}".format(
            symbol, close_price
        ))    
    # ============================================
    # MAIN RUN LOOP
    # ============================================

    async def run(self):
        """
        Main execution loop.

        Sequence:
        1. Check all modules are healthy
        2. Initialize async components
        3. Start Telegram bot polling
        4. Start WebSocket streaming
        5. Start background workers
        6. Run signal cycles every 10 minutes
        7. On shutdown → graceful cleanup
        """
        print("\n" + "★" * 55)
        print("  CRYPTO SIGNAL BOT — LAUNCHING")
        print("★" * 55 + "\n")

        # ── Pre-flight checks ──
        if not self.check_modules():
            print("[MAIN] ❌ Critical modules missing "
                  "— cannot start")
            return

        if not await self.initialize():
            print("[MAIN] ❌ Initialization failed "
                  "— cannot start")
            return

        self.is_running = True
        self.start_time = datetime.now()

        # ────────────────────────────────
        # 1. Start Telegram Bot
        # ────────────────────────────────
        print("[MAIN] 🤖 Starting Telegram Bot API...")
        try:
            await self.app.initialize()
            await self.app.start()
            if self.app.updater:
                await self.app.updater.start_polling(
                    drop_pending_updates=True
                )
            print("[MAIN]   ✅ Telegram Bot Online")
        except Exception as e:
            print("[MAIN]   ❌ Telegram Bot Failed: "
                  "{}".format(e))
            if bot_logger:
                bot_logger.log_error("MAIN.Telegram", e)

        # ────────────────────────────────
        # 2. Start WebSocket
        # ────────────────────────────────
        try:
            if fetcher:
                self._ws_task = asyncio.create_task(
                    fetcher.start_websocket(
                        self.on_candle_close
                    )
                )
                print("[MAIN] 🌐 WebSocket stream started")
        except Exception as e:
            print("[MAIN] ⚠️ WebSocket failed: "
                  "{}".format(e))

        # ────────────────────────────────
        # 3. Start Background Workers
        # ────────────────────────────────
        if REMINDERS_LOADED and reminder_manager:
            self._workers.append(
                asyncio.create_task(self._reminder_worker())
            )

        if AUTH_LOADED and auth_manager:
            self._workers.append(
                asyncio.create_task(
                    self._auth_expiry_worker()
                )
            )

        print("")
        print("[MAIN] " + "━" * 48)
        print("[MAIN]  🚀 BOT IS NOW RUNNING 24/7")
        print("[MAIN]  Signal cycle every {} minutes".format(
            Config.SIGNAL_INTERVAL_MINUTES
        ))
        print("[MAIN]  Payment mode: {}".format(
            Config.PAYMENT_MODE.upper()
        ))
        print("[MAIN]  Press Ctrl+C to stop")
        print("[MAIN] " + "━" * 48)
        print("")

        # ────────────────────────────────
        # 4. Signal Loop (Every N minutes)
        # ────────────────────────────────
        # FIX: Previously this called
        #   signal_sender._get_active_subscribers()
        # instead of self.run_signal_cycle().
        # Now correctly runs the full signal pipeline.
        # ────────────────────────────────
        try:
            while self.is_running:

                # ── Run one full signal cycle ──
                try:
                    await self.run_signal_cycle()
                except Exception as e:
                    print("[MAIN] ❌ Cycle error: "
                          "{}".format(e))
                    if bot_logger:
                        bot_logger.log_error(
                            "MAIN.CycleWrapper", e,
                            tb_info=True
                        )

                # ── Sleep until next cycle ──
                if self.is_running:
                    wait_seconds = (
                        Config.SIGNAL_INTERVAL_MINUTES * 60
                    )
                    next_time = datetime.now() + timedelta(
                        seconds=wait_seconds
                    )
                    print("[MAIN] ⏳ Next cycle in {} min "
                          "(at {})\n".format(
                              Config.SIGNAL_INTERVAL_MINUTES,
                              next_time.strftime("%H:%M:%S"),
                          ))

                    # Sleep in 1-second chunks for
                    # responsive shutdown
                    for _ in range(wait_seconds):
                        if not self.is_running:
                            break
                        await asyncio.sleep(1)

        except asyncio.CancelledError:
            print("[MAIN] 🛑 Main loop cancelled")
        except KeyboardInterrupt:
            print("\n[MAIN] 🛑 Keyboard interrupt")
        finally:
            await self.shutdown()

    # ============================================
    # GRACEFUL SHUTDOWN
    # ============================================

    async def shutdown(self):
        """
        Gracefully shuts down all components.

        Order matters:
        1. Stop accepting new commands (Telegram)
        2. Stop background workers
        3. Stop WebSocket
        4. Close HTTP connections
        5. Print final statistics
        """
        print("\n" + "=" * 55)
        print("  SHUTTING DOWN CRYPTO SIGNAL BOT")
        print("=" * 55 + "\n")

        self.is_running = False

        # ── 1. Stop Telegram Bot ──
        print("[SHUTDOWN] Stopping Telegram Bot...")
        try:
            if self.app:
                if self.app.updater:
                    await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            print("[SHUTDOWN]   ✅ Telegram Bot stopped")
        except Exception as e:
            print("[SHUTDOWN]   ⚠️ Telegram error: "
                  "{}".format(e))

        # ── 2. Stop Workers ──
        print("[SHUTDOWN] Stopping background workers...")
        for task in self._workers:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        print("[SHUTDOWN]   ✅ {} worker(s) stopped".format(
            len(self._workers)
        ))

        # ── 3. Stop WebSocket ──
        print("[SHUTDOWN] Stopping WebSocket...")
        try:
            if self._ws_task is not None:
                if fetcher:
                    await fetcher.stop_websocket()
                self._ws_task.cancel()
                try:
                    await self._ws_task
                except asyncio.CancelledError:
                    pass
            print("[SHUTDOWN]   ✅ WebSocket stopped")
        except Exception as e:
            print("[SHUTDOWN]   ⚠️ WebSocket error: "
                  "{}".format(e))

        # ── 4. Close HTTP ──
        print("[SHUTDOWN] Closing HTTP connections...")
        try:
            if fetcher:
                await fetcher.close()
            print("[SHUTDOWN]   ✅ HTTP closed")
        except Exception as e:
            print("[SHUTDOWN]   ⚠️ HTTP error: "
                  "{}".format(e))

        # ── 5. Final Statistics ──
        print("\n[SHUTDOWN] ── Final Statistics ──")
        print("[SHUTDOWN]   Cycles run      : {}".format(
            self.cycle_count
        ))
        print("[SHUTDOWN]   Signals total   : {}".format(
            self.signals_generated
        ))

        if self.start_time:
            uptime = datetime.now() - self.start_time
            total_seconds = uptime.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            secs = int(total_seconds % 60)
            print("[SHUTDOWN]   Uptime          : "
                  "{}h {}m {}s".format(hours, minutes, secs))

        if PAYMENT_LOADED and payment_manager:
            stats = payment_manager.get_payment_stats()
            print("[SHUTDOWN]   Payments        : {} total, "
                  "{} completed".format(
                      stats.get("total_payments", 0),
                      stats.get("completed", 0),
                  ))

        if AUTH_LOADED and auth_manager:
            sec_stats = auth_manager.get_security_stats()
            print("[SHUTDOWN]   Active subs     : {}".format(
                sec_stats.get("active_subscriptions", 0)
            ))
            print("[SHUTDOWN]   Tokens issued   : {}".format(
                sec_stats.get("total_tokens", 0)
            ))

        if signal_sender:
            sender_stats = signal_sender.get_stats()
            print("[SHUTDOWN]   Signals sent    : {}".format(
                sender_stats.get("total_sent", 0)
            ))
            print("[SHUTDOWN]   Blocked users   : {}".format(
                sender_stats.get("blocked_users", 0)
            ))

        if bot_logger:
            bot_logger.log_shutdown("User exit")

        print("\n" + "=" * 55)
        print("  ✅ BOT STOPPED SAFELY")
        print("=" * 55 + "\n")


# ==================================================
# ENTRY POINT
# ==================================================

master_bot = CryptoSignalBotMaster()


def handle_signal(sig, frame):
    """OS signal handler for SIGINT/SIGTERM."""
    print("\n[MAIN] ⚠️ Signal {} received "
          "— stopping...".format(sig))
    master_bot.is_running = False


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


async def main():
    """Async entry point."""
    await master_bot.run()


if __name__ == "__main__":
    print("\n[MAIN] Python {} | {}".format(
        sys.version.split()[0], sys.platform
    ))
    print("[MAIN] Working dir: {}".format(os.getcwd()))

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("\n[MAIN] ❌ FATAL: {}".format(e))
        import traceback
        traceback.print_exc()
    finally:
        print("[MAIN] Process ended")    