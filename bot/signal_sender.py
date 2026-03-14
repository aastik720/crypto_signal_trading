# ============================================
# CRYPTO SIGNAL BOT - SIGNAL SENDER
# ============================================
# Distributes trading signals to two channels:
#
# 1. PUBLIC CHANNEL (free preview):
#    - Maximum 2 signals per day
#    - Limited info (no Target 2, no brain details)
#    - Includes premium upsell CTA
#
# 2. PRIVATE SUBSCRIBERS (premium):
#    - Unlimited signals
#    - Full signal details with all targets
#    - Complete 8-brain analysis breakdown
#
# Features:
#    - Priority queue (highest confidence first)
#    - Rate limiting (50ms between sends)
#    - Anti-spam (30s gap between signal batches)
#    - Blocked user detection and cleanup
#    - Daily counter auto-reset at midnight
#    - Graceful error handling (never crashes)
#
# Usage:
#    from bot.signal_sender import signal_sender
#    await signal_sender.distribute_signal(signal_data)
# ============================================

import asyncio
import logging
from datetime import datetime, timedelta, date
from collections import deque

from config.settings import Config

# ============================================
# DATABASE IMPORT (graceful fallback)
# ============================================

try:
    from database.db_manager import db as db_manager
    DB_AVAILABLE = True
except ImportError:
    db_manager = None
    DB_AVAILABLE = False
    print("[SENDER] ⚠️ Database not available — "
          "using in-memory tracking")

# ============================================
# LOGGING
# ============================================

logger = logging.getLogger("signal_sender")


class SignalSender:
    """
    Signal distribution engine.

    Routes trading signals to:
    1. Public Telegram channel (capped at 2/day)
    2. All active premium subscribers (unlimited)

    Includes a priority queue that holds signals
    and sends them in order of confidence score,
    with a 30-second gap between batches to prevent
    user spam.

    Handles Telegram API edge cases:
    - Blocked bots (403 Forbidden)
    - Deleted accounts (400 Bad Request)
    - Rate limits (429 Too Many Requests)
    - Network timeouts
    - Invalid chat IDs

    Attributes:
        bot:                    Telegram bot instance
        channel_id (str):       Public channel ID
        daily_limit (int):      Max public signals per day
        signal_gap (int):       Seconds between signal batches
        send_delay (float):     Seconds between individual sends
        _public_count (int):    Today's public signal count
        _public_date (date):    Date of the count
        _signal_queue (deque):  Priority-sorted signal queue
        _is_sending (bool):     Lock to prevent concurrent sends
        _blocked_users (set):   Users who blocked the bot
        _send_history (list):   Log of all send attempts
    """

    # ============================================
    # BRAIN DISPLAY CONFIGURATION
    # ============================================

    BRAIN_DISPLAY = [
        ("RSI", "RSI", "📊"),
        ("MACD", "MACD", "📈"),
        ("BOLLINGER", "Bollinger", "📉"),
        ("VOLUME", "Volume", "🔊"),
        ("EMA", "EMA Cross", "〰️"),
        ("SUPPORT_RESISTANCE", "S/R Levels", "📏"),
        ("CANDLE_PATTERNS", "Candles", "🕯️"),
        ("OBV", "OBV", "💧"),
        ("VWAP", "VWAP", "💰"),
        ("STOCHASTIC_RSI", "StochRSI", "⚡"),
    ]

    # Direction emoji mapping
    DIR_EMOJI = {
        "LONG": "🟢",
        "SHORT": "🔴",
        "NEUTRAL": "⚪",
    }

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self, bot_instance=None):
        """
        Initialize the Signal Sender.

        Args:
            bot_instance: CryptoSignalBot instance.
                         Can be set later via set_bot().
                         Needed for sending messages.

        Configuration from Config:
        - TELEGRAM_PUBLIC_CHANNEL_ID: channel to post free signals
        - PUBLIC_CHANNEL_DAILY_LIMIT: max signals per day (2)
        - SIGNAL_INTERVAL_MINUTES: gap between signal scans (10)

        Internal state:
        - _public_count resets automatically at midnight
        - _signal_queue sorted by confidence (highest first)
        - _blocked_users tracked to skip on future sends
        """
        # ------ Bot reference ------
        self.bot = bot_instance

        # ------ Channel config ------
        self.channel_id = Config.TELEGRAM_PUBLIC_CHANNEL_ID

        # ------ Limits ------
        try:
            self.daily_limit = int(
                Config.PUBLIC_CHANNEL_DAILY_LIMIT
            )
        except (AttributeError, ValueError, TypeError):
            self.daily_limit = 2

        # ------ Timing ------
        self.signal_gap = 30
        self.send_delay = 0.05
        self.rate_limit_delay = 1.0

        # ------ Daily counter ------
        self._public_count = 0
        self._public_date = date.today()

        # ------ Signal queue ------
        self._signal_queue = deque()
        self._is_sending = False
        self._last_send_time = None

        # ------ Tracking ------
        self._blocked_users = set()
        self._send_history = []
        self._total_sent = 0
        self._total_failed = 0

        print("[SENDER] ✅ Signal Sender initialized")
        print("[SENDER]    Channel: {}".format(
            self.channel_id if self.channel_id
            else "(not set)"
        ))
        print("[SENDER]    Daily limit: {} public "
              "signals".format(self.daily_limit))
        print("[SENDER]    Send delay: {}ms".format(
            int(self.send_delay * 1000)
        ))

    # ============================================
    # FUNCTION 2: SET BOT INSTANCE
    # ============================================

    def set_bot(self, bot_instance):
        """
        Set or update the bot instance.

        Called after bot is built, since the sender
        may be created before the bot is ready.

        Args:
            bot_instance: CryptoSignalBot with application
        """
        self.bot = bot_instance
        print("[SENDER] ✅ Bot instance linked")

    # ============================================
    # FUNCTION 3: DAILY COUNTER MANAGEMENT
    # ============================================

    def _check_daily_reset(self):
        """
        Reset public signal counter if date changed.

        Called before every public channel send.
        Compares stored date with today's date.
        If different → reset counter to 0.
        """
        today = date.today()
        if self._public_date != today:
            old_count = self._public_count
            self._public_count = 0
            self._public_date = today
            print("[SENDER] 🔄 Daily counter reset "
                  "(was {} yesterday)".format(old_count))

    def get_public_count_today(self):
        """
        Get how many public signals sent today.

        Returns:
            int: Number of public signals sent today
        """
        self._check_daily_reset()
        return self._public_count

    def get_public_remaining(self):
        """
        Get remaining public signals for today.

        Returns:
            int: Remaining signals (0 if limit reached)
        """
        self._check_daily_reset()
        return max(0, self.daily_limit - self._public_count)

    # ============================================
    # FUNCTION 4: FORMAT PRIVATE SIGNAL
    # ============================================

    def format_signal_message(self, signal, is_public=False):
        """
        Format a signal into a Telegram message.

        Two formats:
        - PRIVATE (is_public=False): Full signal with
          all targets, brain analysis, and risk/reward
        - PUBLIC (is_public=True): Limited info with
          premium upsell CTA

        Handles missing fields gracefully — every field
        has a fallback default value.

        Args:
            signal (dict): Signal data from SignalEngine
            is_public (bool): True for public channel format

        Returns:
            str: HTML-formatted Telegram message
        """
        try:
            if is_public:
                return self._format_public_signal(signal)
            else:
                return self._format_private_signal(signal)

        except Exception as e:
            print("[SENDER] ❌ Format error: {}".format(e))
            return self._format_fallback_signal(signal)

    def _format_private_signal(self, signal):
        """
        Full private signal format for subscribers.

        Includes:
        - All price targets (Target 1 + Target 2)
        - Complete 8-brain analysis breakdown
        - Risk/reward ratio
        - Agreement level
        - Validity timer

        Args:
            signal (dict): Signal data

        Returns:
            str: HTML-formatted message
        """
        try:
            # ------ Extract fields with defaults ------
            pair = signal.get("pair", "???/USDT")
            direction = signal.get("direction", "NEUTRAL")
            entry = signal.get("entry_price", 0)
            target_1 = signal.get("target_1", 0)
            target_2 = signal.get("target_2", 0)
            stop_loss = signal.get("stop_loss", 0)
            confidence = signal.get("confidence", 0)
            risk_reward = signal.get("risk_reward", 0)
            valid_for = signal.get("valid_for_minutes", 10)
            agreement = signal.get(
                "agreement_level", "MODERATE"
            )
            brains = signal.get("brain_details", {})
            timestamp = signal.get(
                "timestamp",
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M UTC"
                ),
            )

            # ------ Direction styling ------
            if direction == "LONG":
                dir_emoji = "📈"
                dir_label = "LONG ✅"
                header_emoji = "🟢"
            elif direction == "SHORT":
                dir_emoji = "📉"
                dir_label = "SHORT 🔻"
                header_emoji = "🔴"
            else:
                dir_emoji = "⏸️"
                dir_label = "NEUTRAL ⏸️"
                header_emoji = "⚪"

            # ------ Format prices ------
            entry_str = self._format_price(entry)
            t1_str = self._format_price(target_1)
            t2_str = self._format_price(target_2)
            sl_str = self._format_price(stop_loss)

            # ------ Calculate percentages ------
            t1_pct = self._calc_pct(
                entry, target_1, direction
            )
            t2_pct = self._calc_pct(
                entry, target_2, direction
            )
            sl_pct = self._calc_sl_pct(
                entry, stop_loss, direction
            )

            # ------ Confidence bar ------
            conf_bar = self._make_conf_bar(confidence)

            # ------ Agreement emoji ------
            agree_emoji = self._agreement_emoji(agreement)

            # ------ Brain analysis section ------
            brain_section = self._format_brain_analysis(
                brains
            )

            # ------ Timestamp string ------
            if isinstance(timestamp, str):
                time_str = timestamp
            else:
                time_str = timestamp.strftime(
                    "%Y-%m-%d %H:%M UTC"
                )

            # ------ Build message ------
            msg = (
                "{header} <b>⚡ SIGNAL ALERT</b> "
                "{header}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "🪙 <b>Pair</b>      : "
                "<code>{pair}</code>\n"
                "{dir_emoji} <b>Direction</b> : "
                "<b>{dir_label}</b>\n"
                "\n"
                "━━━ 💰 Trade Setup ━━━\n"
                "💰 <b>Entry</b>     : "
                "<code>{entry}</code>\n"
                "🎯 <b>Target 1</b>  : "
                "<code>{t1}</code> ({t1_pct})\n"
                "🎯 <b>Target 2</b>  : "
                "<code>{t2}</code> ({t2_pct})\n"
                "🛑 <b>Stop Loss</b> : "
                "<code>{sl}</code> ({sl_pct})\n"
                "\n"
                "━━━ 📊 Signal Stats ━━━\n"
                "⭐ <b>Confidence</b> : "
                "<b>{conf:.1f}%</b>\n"
                "   [{conf_bar}]\n"
                "📊 <b>Risk/Reward</b>: "
                "<b>{rr:.2f}</b>\n"
                "{agree_emoji} <b>Agreement</b> : "
                "<b>{agreement}</b>\n"
                "⏰ <b>Valid for</b>  : "
                "<b>{valid} min</b>\n"
                "\n"
                "━━━ 🧠 Brain Analysis ━━━\n"
                "{brain_section}\n"
                "\n"
                "⏳ Next scan in {interval} minutes\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "⏰ <i>{time}</i>\n"
                "⚠️ <i>Not financial advice. "
                "Trade at your own risk.</i>"
            ).format(
                header=header_emoji,
                pair=pair,
                dir_emoji=dir_emoji,
                dir_label=dir_label,
                entry=entry_str,
                t1=t1_str,
                t1_pct=t1_pct,
                t2=t2_str,
                t2_pct=t2_pct,
                sl=sl_str,
                sl_pct=sl_pct,
                conf=confidence,
                conf_bar=conf_bar,
                rr=risk_reward,
                agree_emoji=agree_emoji,
                agreement=agreement,
                valid=valid_for,
                brain_section=brain_section,
                interval=Config.SIGNAL_INTERVAL_MINUTES,
                time=time_str,
            )

            return msg

        except Exception as e:
            print("[SENDER] ❌ Private format error: "
                  "{}".format(e))
            return self._format_fallback_signal(signal)

    def _format_public_signal(self, signal):
        """
        Limited public signal format for free channel.

        Shows:
        - Pair, direction, entry, Target 1, stop loss
        - Confidence score
        - Daily count display

        Hides:
        - Target 2 (premium only)
        - Brain analysis (premium only)
        - Risk/reward details

        Includes:
        - Premium upsell CTA

        Args:
            signal (dict): Signal data

        Returns:
            str: HTML-formatted message
        """
        try:
            pair = signal.get("pair", "???/USDT")
            direction = signal.get("direction", "NEUTRAL")
            entry = signal.get("entry_price", 0)
            target_1 = signal.get("target_1", 0)
            stop_loss = signal.get("stop_loss", 0)
            confidence = signal.get("confidence", 0)
            timestamp = signal.get(
                "timestamp",
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M UTC"
                ),
            )

            if direction == "LONG":
                dir_emoji = "📈"
                dir_label = "LONG ✅"
                header_emoji = "🟢"
            elif direction == "SHORT":
                dir_emoji = "📉"
                dir_label = "SHORT 🔻"
                header_emoji = "🔴"
            else:
                dir_emoji = "⏸️"
                dir_label = "NEUTRAL"
                header_emoji = "⚪"

            entry_str = self._format_price(entry)
            t1_str = self._format_price(target_1)
            sl_str = self._format_price(stop_loss)
            t1_pct = self._calc_pct(
                entry, target_1, direction
            )
            sl_pct = self._calc_sl_pct(
                entry, stop_loss, direction
            )
            conf_bar = self._make_conf_bar(confidence)

            # Public count display
            count = self.get_public_count_today()

            # Bot username
            bot_username = "CryptoSignalBot"
            if (self.bot and self.bot.application and
                    self.bot.application.bot):
                try:
                    uname = self.bot.application.bot.username
                    if uname:
                        bot_username = uname
                except Exception:
                    pass

            # Timestamp string
            if isinstance(timestamp, str):
                time_str = timestamp
            else:
                time_str = timestamp.strftime(
                    "%Y-%m-%d %H:%M UTC"
                )

            msg = (
                "{header} <b>⚡ FREE SIGNAL ALERT</b> "
                "{header}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "🪙 <b>Pair</b>      : "
                "<code>{pair}</code>\n"
                "{dir_emoji} <b>Direction</b> : "
                "<b>{dir_label}</b>\n"
                "💰 <b>Entry</b>     : "
                "<code>{entry}</code>\n"
                "🎯 <b>Target 1</b>  : "
                "<code>{t1}</code> ({t1_pct})\n"
                "🛑 <b>Stop Loss</b> : "
                "<code>{sl}</code> ({sl_pct})\n"
                "⭐ <b>Confidence</b> : "
                "<b>{conf:.1f}%</b>\n"
                "   [{conf_bar}]\n"
                "\n"
                "🔒 <b>Get Target 2 + Full Brain "
                "Analysis</b>\n"
                "   <b>with Premium!</b> "
                "₹{price}/{days} days\n"
                "\n"
                "📊 {count}/{limit} free signals today\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 @{bot_name}\n"
                "⏰ <i>{time}</i>\n"
                "⚠️ <i>Not financial advice.</i>"
            ).format(
                header=header_emoji,
                pair=pair,
                dir_emoji=dir_emoji,
                dir_label=dir_label,
                entry=entry_str,
                t1=t1_str,
                t1_pct=t1_pct,
                sl=sl_str,
                sl_pct=sl_pct,
                conf=confidence,
                conf_bar=conf_bar,
                price=Config.SUBSCRIPTION_PRICE,
                days=Config.SUBSCRIPTION_DAYS,
                count=count + 1,
                limit=self.daily_limit,
                bot_name=bot_username,
                time=time_str,
            )

            return msg

        except Exception as e:
            print("[SENDER] ❌ Public format error: "
                  "{}".format(e))
            return self._format_fallback_signal(signal)

    # ============================================
    # FORMATTING HELPERS
    # ============================================

    def _format_price(self, price):
        """
        Format a price value for display.

        Rules:
        - >= $1000:   $67,500.00
        - >= $1:      $3.4521
        - >= $0.01:   $0.0854
        - < $0.01:    $0.000012
        - 0 or None:  N/A

        Args:
            price: Price value (float, int, or None)

        Returns:
            str: Formatted price string
        """
        try:
            if not price or price == 0:
                return "N/A"

            price = float(price)

            if price >= 1000:
                return "${:,.2f}".format(price)
            elif price >= 1:
                return "${:.4f}".format(price)
            elif price >= 0.01:
                return "${:.4f}".format(price)
            else:
                return "${:.6f}".format(price)

        except (ValueError, TypeError):
            return "N/A"

    def _calc_pct(self, entry, target, direction):
        """
        Calculate target percentage from entry.

        Args:
            entry (float):      Entry price
            target (float):     Target price
            direction (str):    LONG or SHORT

        Returns:
            str: Formatted percentage like "+2.50%"
        """
        try:
            if not entry or not target or entry == 0:
                return "N/A"

            entry = float(entry)
            target = float(target)
            pct = ((target - entry) / entry) * 100

            return "{:+.2f}%".format(pct)

        except (ValueError, TypeError, ZeroDivisionError):
            return "N/A"

    def _calc_sl_pct(self, entry, stop, direction):
        """
        Calculate stop loss percentage from entry.

        Args:
            entry (float):  Entry price
            stop (float):   Stop loss price
            direction (str): LONG or SHORT

        Returns:
            str: Formatted percentage like "-1.50%"
        """
        try:
            if not entry or not stop or entry == 0:
                return "N/A"

            entry = float(entry)
            stop = float(stop)
            pct = ((stop - entry) / entry) * 100

            return "{:+.2f}%".format(pct)

        except (ValueError, TypeError, ZeroDivisionError):
            return "N/A"

    def _make_conf_bar(self, confidence):
        """
        Create a visual confidence bar.

        100% = ██████████ (10 filled)
          0% = ░░░░░░░░░░ (10 empty)

        Args:
            confidence (float): 0-100

        Returns:
            str: Bar string like "████████░░"
        """
        try:
            conf = max(0, min(100, float(confidence)))
            filled = int(conf / 10)
            empty = 10 - filled
            return "█" * filled + "░" * empty

        except (ValueError, TypeError):
            return "░" * 10

    def _agreement_emoji(self, agreement):
        """
        Get emoji for agreement level.

        Args:
            agreement (str): STRONG, MODERATE, WEAK,
                            MIXED

        Returns:
            str: Appropriate emoji
        """
        mapping = {
            "STRONG": "💪",
            "MODERATE": "👍",
            "WEAK": "👌",
            "MIXED": "⚠️",
        }
        return mapping.get(
            str(agreement).upper(), "📊"
        )

    def _format_brain_analysis(self, brains):
        """
        Format the 8-brain analysis section.

        Args:
            brains (dict): Brain results by brain name

        Returns:
            str: Formatted multi-line string
        """
        try:
            if not brains:
                return ("  <i>(analysis details "
                        "not available)</i>")

            lines = []

            for brain_key, display_name, emoji in \
                    self.BRAIN_DISPLAY:
                brain_data = brains.get(brain_key, {})

                if brain_data:
                    b_dir = brain_data.get(
                        "direction", "N/A"
                    )
                    b_conf = brain_data.get(
                        "confidence", 0
                    )
                    dir_dot = self.DIR_EMOJI.get(
                        b_dir, "⚪"
                    )

                    lines.append(
                        "  {emoji} {name}: {dot} "
                        "{dir} ({conf}%)".format(
                            emoji=emoji,
                            name=display_name,
                            dot=dir_dot,
                            dir=b_dir,
                            conf=b_conf,
                        )
                    )
                else:
                    lines.append(
                        "  {emoji} {name}: "
                        "⚪ N/A".format(
                            emoji=emoji,
                            name=display_name,
                        )
                    )

            return "\n".join(lines)

        except Exception as e:
            print("[SENDER] ❌ Brain format error: "
                  "{}".format(e))
            return "  <i>(brain details unavailable)</i>"

    def _format_fallback_signal(self, signal):
        """
        Fallback signal format when normal
        formatting fails.

        Args:
            signal (dict): Signal data

        Returns:
            str: Simple formatted message
        """
        try:
            return (
                "📊 <b>Signal Alert</b>\n\n"
                "Pair: {pair}\n"
                "Direction: {direction}\n"
                "Confidence: {conf}%\n"
                "Entry: {entry}\n\n"
                "<i>(Detailed formatting "
                "unavailable)</i>"
            ).format(
                pair=signal.get("pair", "?"),
                direction=signal.get("direction", "?"),
                conf=signal.get("confidence", 0),
                entry=signal.get("entry_price", "?"),
            )
        except Exception:
            return ("📊 Signal Alert — "
                    "details unavailable")
    # ============================================
    # FUNCTION 5: SEND TO PUBLIC CHANNEL
    # ============================================

    async def send_to_public_channel(self, signal):
        """
        Send signal to the public Telegram channel.

        Checks:
        1. Channel ID is configured
        2. Bot application is ready
        3. Daily limit not reached

        Args:
            signal (dict): Signal data from SignalEngine

        Returns:
            bool: True if sent, False if skipped/error
        """
        try:
            # ------ Pre-checks ------
            if not self.channel_id:
                print("[SENDER] ⚠️ No channel ID — "
                      "skipping public send")
                return False

            if not self.bot:
                print("[SENDER] ⚠️ No bot instance — "
                      "skipping public send")
                return False

            if (not self.bot.application or
                    not self.bot.application.bot):
                print("[SENDER] ⚠️ Bot application "
                      "not ready")
                return False

            # ------ Check daily limit ------
            self._check_daily_reset()

            if self._public_count >= self.daily_limit:
                print("[SENDER] ⏸️ Daily public limit "
                      "reached ({}/{})".format(
                          self._public_count,
                          self.daily_limit,
                      ))
                return False

            # ------ Format message ------
            message = self.format_signal_message(
                signal, is_public=True
            )

            # ------ Send to channel ------
            await self.bot.application.bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode="HTML",
            )

            # ------ Update counter ------
            self._public_count += 1
            remaining = (
                self.daily_limit - self._public_count
            )

            # ------ Log ------
            self._log_send(
                target="PUBLIC_CHANNEL",
                signal=signal,
                success=True,
            )

            print("[SENDER] 📢 Public signal sent! "
                  "{pair} {dir} ({conf}%) — "
                  "{remain} remaining today".format(
                      pair=signal.get("pair", "?"),
                      dir=signal.get("direction", "?"),
                      conf=signal.get("confidence", 0),
                      remain=remaining,
                  ))

            return True

        except Exception as e:
            error_type = type(e).__name__
            print("[SENDER] ❌ Public channel error "
                  "[{}]: {}".format(error_type, e))

            self._log_send(
                target="PUBLIC_CHANNEL",
                signal=signal,
                success=False,
                error=str(e),
            )

            return False

    # ============================================
    # FUNCTION 6: SEND TO PRIVATE USERS
    # ============================================

    async def send_to_private_users(self, signal):
        """
        Send full signal to ALL active subscribers.

        Args:
            signal (dict): Signal data from SignalEngine

        Returns:
            dict: sent/failed/blocked/total/errors
        """
        result = {
            "sent": 0,
            "failed": 0,
            "blocked": 0,
            "total": 0,
            "errors": [],
        }

        try:
            # ------ Pre-checks ------
            if not self.bot:
                print("[SENDER] ⚠️ No bot instance")
                return result

            if (not self.bot.application or
                    not self.bot.application.bot):
                print("[SENDER] ⚠️ Bot application "
                      "not ready")
                return result

            # ------ Get active subscribers ------
            subscribers = (
                await self._get_active_subscribers()
            )

            # Remove known blocked users
            active_subs = [
                cid for cid in subscribers
                if cid not in self._blocked_users
            ]

            result["total"] = len(active_subs)

            if not active_subs:
                print("[SENDER] ℹ️ No active subscribers")
                return result

            print("[SENDER] 📡 Sending to {} "
                  "subscriber(s)...".format(
                      len(active_subs)
                  ))

            # ------ Format message once ------
            message = self.format_signal_message(
                signal, is_public=False
            )

            # ------ Send to each user ------
            for chat_id in active_subs:
                send_ok = await self._send_to_user(
                    chat_id, message, signal
                )

                if send_ok == "sent":
                    result["sent"] += 1
                elif send_ok == "blocked":
                    result["blocked"] += 1
                    result["failed"] += 1
                else:
                    result["failed"] += 1
                    result["errors"].append(
                        "Failed: {}".format(chat_id)
                    )

                # Rate limit delay
                await asyncio.sleep(self.send_delay)

            print("[SENDER] 📡 Private send complete: "
                  "{sent}/{total} sent, "
                  "{failed} failed, "
                  "{blocked} blocked".format(**result))

            return result

        except Exception as e:
            print("[SENDER] ❌ Private send error: "
                  "{}".format(e))
            result["errors"].append(str(e))
            return result

    async def _send_to_user(self, chat_id, message,
                            signal):
        """
        Send a formatted message to a single user.

        Handles all Telegram API errors.

        Args:
            chat_id (int):    Target user's chat ID
            message (str):    Formatted HTML message
            signal (dict):    Signal data (for logging)

        Returns:
            str: "sent", "blocked", or "failed"
        """
        try:
            await self.bot.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML",
            )

            # Increment signal count
            await self._increment_signal_count(chat_id)

            self._log_send(
                target="USER:{}".format(chat_id),
                signal=signal,
                success=True,
            )

            return "sent"

        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__

            # ------ Blocked by user ------
            if ("forbidden" in error_str or
                    "blocked" in error_str or
                    "deactivated" in error_str or
                    "kicked" in error_str):

                self._blocked_users.add(chat_id)
                print("[SENDER] 🚫 User {} blocked "
                      "bot — marked".format(chat_id))

                self._log_send(
                    target="USER:{}".format(chat_id),
                    signal=signal,
                    success=False,
                    error="BLOCKED",
                )

                return "blocked"

            # ------ Bad request ------
            elif ("bad request" in error_str or
                  "chat not found" in error_str or
                  "user not found" in error_str):

                self._blocked_users.add(chat_id)
                print("[SENDER] ⚠️ User {} — bad "
                      "request/not found".format(chat_id))

                self._log_send(
                    target="USER:{}".format(chat_id),
                    signal=signal,
                    success=False,
                    error="NOT_FOUND",
                )

                return "blocked"

            # ------ Rate limited ------
            elif ("too many requests" in error_str or
                  "retry" in error_str or
                  "429" in error_str):

                print("[SENDER] ⏳ Rate limited — "
                      "waiting {}s".format(
                          self.rate_limit_delay
                      ))
                await asyncio.sleep(
                    self.rate_limit_delay
                )

                # Retry once
                try:
                    await self.bot.application.bot \
                        .send_message(
                            chat_id=chat_id,
                            text=message,
                            parse_mode="HTML",
                        )
                    await self._increment_signal_count(
                        chat_id
                    )
                    return "sent"
                except Exception:
                    return "failed"

            # ------ Other errors ------
            else:
                print("[SENDER] ❌ Send to {} failed "
                      "[{}]: {}".format(
                          chat_id, error_type, e
                      ))

                self._log_send(
                    target="USER:{}".format(chat_id),
                    signal=signal,
                    success=False,
                    error=str(e)[:100],
                )

                return "failed"

    # ============================================
    # FUNCTION 7: DISTRIBUTE SIGNAL (MAIN)
    # ============================================

    async def distribute_signal(self, signal):
        """
        MAIN DISTRIBUTION FUNCTION.

        Called by the scheduler/signal engine when a
        new signal is generated.

        Args:
            signal (dict): Signal data from SignalEngine

        Returns:
            dict: Distribution summary
        """
        summary = {
            "signal": signal,
            "sent_public": False,
            "private_users_sent": 0,
            "private_users_failed": 0,
            "private_users_blocked": 0,
            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "errors": [],
        }

        try:
            # ------ Validate signal ------
            if not signal:
                print("[SENDER] ⚠️ Empty signal — "
                      "skipping")
                summary["errors"].append("Empty signal")
                return summary

            required = [
                "pair", "direction", "confidence"
            ]
            for field in required:
                if field not in signal:
                    print("[SENDER] ⚠️ Missing '{}' in "
                          "signal".format(field))
                    summary["errors"].append(
                        "Missing: {}".format(field)
                    )
                    return summary

            pair = signal.get("pair", "?")
            direction = signal.get("direction", "?")
            confidence = signal.get("confidence", 0)

            print("\n[SENDER] "
                  "══════════════════════════════")
            print("[SENDER]  📡 Distributing Signal")
            print("[SENDER]  Pair: {} | Dir: {} | "
                  "Conf: {}%".format(
                      pair, direction, confidence
                  ))
            print("[SENDER] "
                  "══════════════════════════════")

            # ------ Anti-spam gap check ------
            if self._last_send_time:
                elapsed = (
                    datetime.now() - self._last_send_time
                ).total_seconds()

                if elapsed < self.signal_gap:
                    wait = self.signal_gap - elapsed
                    print("[SENDER] ⏳ Anti-spam wait: "
                          "{:.0f}s".format(wait))
                    await asyncio.sleep(wait)

            # ------ 1. Public Channel ------
            print("[SENDER] → Step 1: Public "
                  "channel...")
            sent_public = (
                await self.send_to_public_channel(signal)
            )
            summary["sent_public"] = sent_public

            # Small delay between public and private
            if sent_public:
                await asyncio.sleep(0.5)

            # ------ 2. Private Subscribers ------
            print("[SENDER] → Step 2: Private "
                  "subscribers...")
            private_result = (
                await self.send_to_private_users(signal)
            )

            summary["private_users_sent"] = (
                private_result["sent"]
            )
            summary["private_users_failed"] = (
                private_result["failed"]
            )
            summary["private_users_blocked"] = (
                private_result["blocked"]
            )
            summary["errors"].extend(
                private_result["errors"]
            )

            # ------ Update tracking ------
            self._last_send_time = datetime.now()
            self._total_sent += private_result["sent"]
            self._total_failed += private_result["failed"]

            # ------ Record history ------
            history_entry = {
                "pair": pair,
                "direction": direction,
                "confidence": confidence,
                "public_sent": sent_public,
                "private_sent": private_result["sent"],
                "private_failed": (
                    private_result["failed"]
                ),
                "timestamp": summary["timestamp"],
            }
            self._send_history.append(history_entry)

            # Keep history bounded
            if len(self._send_history) > 100:
                self._send_history = (
                    self._send_history[-100:]
                )

            # ------ Summary log ------
            print("\n[SENDER] "
                  "══════════════════════════════")
            print("[SENDER]  📡 Distribution Complete")
            print("[SENDER]  Public : {}".format(
                "✅ Sent" if sent_public
                else "⏸️ Skipped"
            ))
            print("[SENDER]  Private: {}/{} sent".format(
                private_result["sent"],
                private_result["total"],
            ))
            print("[SENDER]  Blocked: {}".format(
                private_result["blocked"]
            ))
            print("[SENDER]  Errors : {}".format(
                len(summary["errors"])
            ))
            print("[SENDER]  Total lifetime: {} sent, "
                  "{} failed".format(
                      self._total_sent,
                      self._total_failed,
                  ))
            print("[SENDER] "
                  "══════════════════════════════\n")

            return summary

        except Exception as e:
            print("[SENDER] ❌ Distribution error: "
                  "{}".format(e))
            summary["errors"].append(str(e))
            return summary

    # ============================================
    # FUNCTION 8: SIGNAL QUEUE
    # ============================================

    async def queue_signal(self, signal):
        """
        Add a signal to the priority queue.

        Signals are sorted by confidence (highest
        first). Prevents duplicates.

        Args:
            signal (dict): Signal data

        Returns:
            bool: True if queued, False if
                  duplicate/invalid
        """
        try:
            if not signal:
                return False

            pair = signal.get("pair", "")
            direction = signal.get("direction", "")
            confidence = signal.get("confidence", 0)

            # Check for duplicate in queue
            for queued in self._signal_queue:
                if (queued.get("pair") == pair and
                        queued.get("direction") ==
                        direction):
                    print("[SENDER] ⏭️ Duplicate signal "
                          "skipped: {} {}".format(
                              pair, direction
                          ))
                    return False

            # Add timestamp if missing
            if "timestamp" not in signal:
                signal["timestamp"] = (
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

            # Insert sorted by confidence
            inserted = False
            for i, queued in enumerate(
                    self._signal_queue):
                if confidence > queued.get(
                        "confidence", 0):
                    self._signal_queue.insert(i, signal)
                    inserted = True
                    break

            if not inserted:
                self._signal_queue.append(signal)

            print("[SENDER] 📥 Signal queued: "
                  "{} {} ({:.0f}%) — Queue size: "
                  "{}".format(
                      pair, direction, confidence,
                      len(self._signal_queue),
                  ))

            return True

        except Exception as e:
            print("[SENDER] ❌ Queue error: "
                  "{}".format(e))
            return False

    async def process_queue(self):
        """
        Process all signals in the queue.

        Highest confidence signals are sent first.

        Returns:
            int: Number of signals processed
        """
        processed = 0

        try:
            if self._is_sending:
                print("[SENDER] ⏳ Already sending — "
                      "skipping queue process")
                return 0

            if not self._signal_queue:
                return 0

            self._is_sending = True

            print("[SENDER] 📤 Processing queue "
                  "({} signals)...".format(
                      len(self._signal_queue)
                  ))

            while self._signal_queue:
                signal = self._signal_queue.popleft()

                await self.distribute_signal(signal)
                processed += 1

                # Gap between signals
                if self._signal_queue:
                    print("[SENDER] ⏳ Waiting {}s "
                          "before next signal...".format(
                              self.signal_gap
                          ))
                    await asyncio.sleep(self.signal_gap)

            print("[SENDER] ✅ Queue processed: "
                  "{} signal(s) distributed".format(
                      processed
                  ))

        except Exception as e:
            print("[SENDER] ❌ Queue processing "
                  "error: {}".format(e))

        finally:
            self._is_sending = False

        return processed

    # ============================================
    # FUNCTION 9: CUSTOM MESSAGE
    # ============================================

    async def send_custom_message(self, chat_id,
                                  message):
        """
        Send a custom message to a specific user.

        Args:
            chat_id (int): Target chat ID
            message (str): HTML-formatted message

        Returns:
            bool: True if sent successfully
        """
        try:
            if not self.bot:
                print("[SENDER] ⚠️ No bot instance")
                return False

            if (not self.bot.application or
                    not self.bot.application.bot):
                print("[SENDER] ⚠️ Bot not ready")
                return False

            if chat_id in self._blocked_users:
                print("[SENDER] ⏭️ User {} is blocked "
                      "— skipping".format(chat_id))
                return False

            await self.bot.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML",
            )

            print("[SENDER] 📨 Custom message sent "
                  "to {}".format(chat_id))
            return True

        except Exception as e:
            error_str = str(e).lower()
            if ("forbidden" in error_str or
                    "blocked" in error_str):
                self._blocked_users.add(chat_id)
                print("[SENDER] 🚫 User {} blocked "
                      "— marked".format(chat_id))
            else:
                print("[SENDER] ❌ Custom message "
                      "error: {}".format(e))
            return False

    # ============================================
    # FUNCTION 10: BROADCAST TO ALL
    # ============================================

    async def broadcast_to_all(self, message):
        """
        Send a message to ALL registered users.

        Args:
            message (str): HTML-formatted message

        Returns:
            dict: {"sent": int, "failed": int,
                   "total": int}
        """
        result = {
            "sent": 0, "failed": 0, "total": 0
        }

        try:
            if not self.bot:
                print("[SENDER] ⚠️ No bot instance")
                return result

            if (not self.bot.application or
                    not self.bot.application.bot):
                print("[SENDER] ⚠️ Bot not ready")
                return result

            # Get ALL users
            all_users = await self._get_all_users()
            result["total"] = len(all_users)

            if not all_users:
                print("[SENDER] ℹ️ No users to "
                      "broadcast to")
                return result

            print("[SENDER] 📢 Broadcasting to {} "
                  "user(s)...".format(len(all_users)))

            for chat_id in all_users:
                if chat_id in self._blocked_users:
                    result["failed"] += 1
                    continue

                try:
                    await self.bot.application.bot \
                        .send_message(
                            chat_id=chat_id,
                            text=message,
                            parse_mode="HTML",
                        )
                    result["sent"] += 1

                except Exception as e:
                    result["failed"] += 1
                    error_str = str(e).lower()
                    if ("forbidden" in error_str or
                            "blocked" in error_str):
                        self._blocked_users.add(chat_id)

                await asyncio.sleep(self.send_delay)

            print("[SENDER] 📢 Broadcast complete: "
                  "{sent}/{total} sent".format(
                      **result
                  ))

            return result

        except Exception as e:
            print("[SENDER] ❌ Broadcast error: "
                  "{}".format(e))
            return result

    # ============================================
    # FUNCTION 11: SEND EXPIRY WARNINGS
    # ============================================

    async def send_expiry_warnings(self,
                                   days_before=3):
        """
        Send subscription expiry warnings.

        Args:
            days_before (int): Warn N days before

        Returns:
            int: Number of warnings sent
        """
        sent = 0

        try:
            subscribers = (
                await self._get_active_subscribers()
            )

            for chat_id in subscribers:
                sub = await self._get_subscription(
                    chat_id
                )
                if not sub:
                    continue

                end_str = sub.get("end_date", "")
                try:
                    if isinstance(end_str, str):
                        end_date = datetime.strptime(
                            end_str,
                            "%Y-%m-%d %H:%M:%S",
                        )
                    else:
                        end_date = end_str

                    days_left = (
                        end_date - datetime.now()
                    ).days

                    if 0 < days_left <= days_before:
                        msg = (
                            "⏳ <b>Subscription Expiry "
                            "Warning</b>\n\n"
                            "Your subscription expires "
                            "in <b>{} day(s)</b>!\n\n"
                            "📅 Expiry: <b>{}</b>\n\n"
                            "Renew now to keep receiving "
                            "premium signals without "
                            "interruption.\n\n"
                            "💎 Renew: ₹{}/{} days"
                        ).format(
                            days_left,
                            end_date.strftime(
                                "%d %b %Y"
                            ),
                            Config.SUBSCRIPTION_PRICE,
                            Config.SUBSCRIPTION_DAYS,
                        )

                        ok = (
                            await self.send_custom_message(
                                chat_id, msg
                            )
                        )
                        if ok:
                            sent += 1

                except (ValueError, TypeError):
                    continue

            if sent > 0:
                print("[SENDER] ⏳ Sent {} expiry "
                      "warning(s)".format(sent))

            return sent

        except Exception as e:
            print("[SENDER] ❌ Expiry warnings "
                  "error: {}".format(e))
            return sent  
    # ============================================
    # DATABASE HELPERS (FIXED — 3 corrupted lines)
    # ============================================

    async def _get_active_subscribers(self):
        """
        Get all active subscriber chat IDs.

        Tries database first, falls back to
        auth_manager, then bot memory.

        Returns:
            list[int]: Active subscriber chat IDs
        """
        try:
            # ── Primary: Database ──
            if DB_AVAILABLE and db_manager:
                try:
                    subs = await db_manager.get_active_subscribers()
                    if subs:
                        return subs
                except Exception:
                    pass

            # ── Fallback 1: Auth manager ──
            try:
                from security.auth import auth_manager
                if auth_manager:
                    active_ids = []
                    for chat_id, sub_data in \
                            auth_manager._subscriptions.items():
                        if sub_data.get("is_active", False):
                            active_ids.append(int(chat_id))
                    if active_ids:
                        return active_ids
            except Exception:
                pass

            # ── Fallback 2: Bot memory ──
            if self.bot:
                try:
                    if hasattr(self.bot, '_mem_users'):
                        return list(
                            self.bot._mem_users.keys()
                        )
                except Exception:
                    pass

            return []

        except Exception:
            return []

    async def _get_all_users(self):
        """
        Get ALL registered user chat IDs.

        Returns:
            list[int]: All user chat IDs
        """
        try:
            # ── Primary: Database ──
            if DB_AVAILABLE and db_manager:
                try:
                    users = await db_manager.get_all_users()
                    if users:
                        return users
                except Exception:
                    pass

            # ── Fallback: Bot memory ──
            if self.bot:
                try:
                    if hasattr(self.bot, '_mem_users'):
                        return list(
                            self.bot._mem_users.keys()
                        )
                except Exception:
                    pass

            return []

        except Exception:
            return []

    async def _get_subscription(self, chat_id):
        """
        Get subscription data for a user.

        Args:
            chat_id (int): User's chat ID

        Returns:
            dict or None: Subscription data
        """
        try:
            # ── Primary: Database ──
            if DB_AVAILABLE and db_manager:
                try:
                    sub = await db_manager.get_subscription(
                        chat_id
                    )
                    if sub:
                        return sub
                except Exception:
                    pass

            # ── Fallback: Auth manager ──
            try:
                from security.auth import auth_manager
                if auth_manager:
                    sub_data = (
                        auth_manager._subscriptions.get(
                            int(chat_id)
                        )
                    )
                    if sub_data:
                        return sub_data
            except Exception:
                pass

            return None

        except Exception:
            return None

    async def _increment_signal_count(self, chat_id):
        """
        Increment signal received count for a user.

        Args:
            chat_id (int): User's chat ID
        """
        try:
            # ── Primary: Database ──
            if DB_AVAILABLE and db_manager:
                try:
                    await db_manager.increment_signal_count(
                        chat_id
                    )
                    return
                except Exception:
                    pass

            # ── Fallback: silently skip ──
            # Signal count is nice-to-have, not critical

        except Exception:
            pass

    def _log_send(self, target, signal, success,
                  error=None):
        """
        Log a send attempt for debugging.

        Args:
            target (str):   "PUBLIC_CHANNEL" or
                           "USER:12345"
            signal (dict):  Signal data
            success (bool): Whether send succeeded
            error (str):    Error message if failed
        """
        try:
            entry = {
                "target": target,
                "pair": signal.get("pair", "?"),
                "direction": signal.get(
                    "direction", "?"
                ),
                "confidence": signal.get(
                    "confidence", 0
                ),
                "success": success,
                "error": error,
                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }

            logger.info(
                "Signal {} | {} | {} {} ({:.0f}%) "
                "| {}".format(
                    "✅" if success else "❌",
                    target,
                    entry["pair"],
                    entry["direction"],
                    entry["confidence"],
                    error or "OK",
                )
            )

        except Exception:
            pass

    # ============================================
    # FUNCTION 12: STATISTICS
    # ============================================

    def get_stats(self):
        """
        Get sender statistics.

        Returns:
            dict: Current stats
        """
        self._check_daily_reset()

        return {
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "public_today": self._public_count,
            "public_remaining": (
                self.get_public_remaining()
            ),
            "daily_limit": self.daily_limit,
            "queue_size": len(self._signal_queue),
            "is_sending": self._is_sending,
            "blocked_users": len(self._blocked_users),
            "history_count": len(self._send_history),
            "last_send": (
                self._last_send_time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ) if self._last_send_time else "Never"
            ),
        }

    def get_history(self, limit=10):
        """
        Get recent send history.

        Args:
            limit (int): Maximum entries to return

        Returns:
            list[dict]: Recent send history entries
        """
        return self._send_history[-limit:]


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

signal_sender = SignalSender()

print("[SENDER] ✅ Signal Sender module loaded and ready")                  