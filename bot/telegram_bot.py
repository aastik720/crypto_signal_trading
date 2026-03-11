# ============================================
# CRYPTO SIGNAL BOT - TELEGRAM BOT INTERFACE
# ============================================
# User-facing Telegram bot that handles:
#   - User registration (/start)
#   - Token activation (inline keyboard flow)
#   - Subscription management
#   - Signal delivery to subscribers
#   - Public channel posting
#
# Uses python-telegram-bot v20+ (async)
#
# Token modes (from .env PAYMENT_MODE):
#   "fake" → bot generates free test token
#   "real" → shows Razorpay payment link
#
# Commands:
#   /start  → welcome + registration
#   /status → subscription status
#   /help   → usage guide + FAQ
#   /cancel → cancel current operation
#
# Inline Buttons:
#   🔑 Activate Token → ConversationHandler flow
#   📊 My Status      → subscription details
#   💰 Get Premium    → fake token or payment link
#   ℹ️ Help           → bot guide
#
# Usage:
#   from bot.telegram_bot import crypto_bot
#   crypto_bot.run()
# ============================================

import uuid
import asyncio
import logging
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

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
    print("[BOT] ⚠️ Database module not available — "
          "using in-memory storage")

# ============================================
# LOGGING
# ============================================

logger = logging.getLogger("telegram_bot")

# ============================================
# CONVERSATION STATES
# ============================================

WAITING_FOR_TOKEN = 0


class CryptoSignalBot:
    """
    Main Telegram bot for the CryptoSignal system.

    Handles all user interactions:
    - Registration and welcome flow
    - Token generation (fake mode) and activation
    - Subscription status checking
    - Signal delivery to subscribers and channel
    - Error handling and logging

    The bot uses ConversationHandler for the token
    activation flow (multi-step interaction) and
    CallbackQueryHandler for inline button routing.

    Attributes:
        application (Application): telegram-bot Application
        token (str):               Bot API token
        channel_id (str):          Public channel ID
        payment_mode (str):        "fake" or "real"
        _mem_users (dict):         In-memory user fallback
        _mem_tokens (dict):        In-memory token fallback
        _mem_subs (dict):          In-memory subscription fallback
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize the Crypto Signal Bot.

        Loads configuration from Config:
        - Bot token for Telegram API
        - Public channel ID for signal broadcasting
        - Payment mode (fake/real)
        - Subscription price and duration

        Sets up in-memory fallback storage in case
        the database module is not available.
        """
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.channel_id = Config.TELEGRAM_PUBLIC_CHANNEL_ID
        self.payment_mode = Config.PAYMENT_MODE
        self.application = None

        # ------ In-memory fallback storage ------
        self._mem_users = {}
        self._mem_tokens = {}
        self._mem_subs = {}
        self._mem_signals_count = {}

        # ------ Validate bot token ------
        if not self.token:
            print("[BOT] ❌ TELEGRAM_BOT_TOKEN is empty!")
        else:
            masked = self.token[:4] + "****" + self.token[-4:]
            print("[BOT] ✅ Bot initialized | Token: {}".format(masked))

        print("[BOT] ✅ Payment mode: {}".format(
            self.payment_mode.upper()
        ))
        print("[BOT] ✅ Channel ID: {}".format(
            self.channel_id if self.channel_id else "(not set)"
        ))

    # ============================================
    # FUNCTION 2: MAIN KEYBOARD
    # ============================================

    def _get_main_keyboard(self):
        """
        Build the main inline keyboard shown after /start.

        Layout:
        ┌──────────────────┬──────────────┐
        │ 🔑 Activate Token│ 📊 My Status │
        ├──────────────────┼──────────────┤
        │ 💰 Get Premium   │ ℹ️ Help      │
        └──────────────────┴──────────────┘

        Returns:
            InlineKeyboardMarkup: The keyboard markup
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔑 Activate Token",
                    callback_data="activate_token"
                ),
                InlineKeyboardButton(
                    "📊 My Status",
                    callback_data="my_status"
                ),
            ],
            [
                InlineKeyboardButton(
                    "💰 Get Premium",
                    callback_data="get_premium"
                ),
                InlineKeyboardButton(
                    "ℹ️ Help",
                    callback_data="help"
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    # ============================================
    # DATABASE WRAPPER METHODS
    # ============================================

    async def _db_add_user(self, chat_id, username, first_name):
        """
        Register a new user in the database.

        Falls back to in-memory storage if database
        is not available.

        Args:
            chat_id (int):     Telegram chat ID
            username (str):    Telegram username
            first_name (str):  User's first name

        Returns:
            bool: True if added or already exists
        """
        try:
            if DB_AVAILABLE and db_manager:
                try:
                    await db_manager.add_user(chat_id, username, first_name)
                    return True
                except TypeError:
                    await db_manager.add_user(
                        chat_id=chat_id,
                        username=username,
                        first_name=first_name
                    )
                    return True
            else:
                if chat_id not in self._mem_users:
                    self._mem_users[chat_id] = {
                        "chat_id": chat_id,
                        "username": username or "",
                        "first_name": first_name or "User",
                        "joined_at": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }
                return True

        except Exception as e:
            print("[BOT] ❌ DB add_user error: {}".format(e))
            self._mem_users[chat_id] = {
                "chat_id": chat_id,
                "username": username or "",
                "first_name": first_name or "User",
                "joined_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
            return True

    async def _db_get_user(self, chat_id):
        """
        Get user data from database or memory.

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            dict or None: User data dictionary
        """
        try:
            if DB_AVAILABLE and db_manager:
                try:
                    user = await db_manager.get_user(chat_id)
                    if user:
                        return user
                except Exception:
                    pass

            return self._mem_users.get(chat_id)

        except Exception as e:
            print("[BOT] ❌ DB get_user error: {}".format(e))
            return self._mem_users.get(chat_id)

    async def _db_create_token(self, chat_id=None):
        """
        Generate a new activation token.

        Creates a UUID-format token and stores it in
        the database with a 28-day expiry.

        Args:
            chat_id (int, optional): Associate with user

        Returns:
            str or None: The generated token string
        """
        try:
            token_str = str(uuid.uuid4()).upper()
            expiry = datetime.now() + timedelta(
                days=Config.SUBSCRIPTION_DAYS
            )

            if DB_AVAILABLE and db_manager:
                try:
                    await db_manager.create_token(
                        token_str,
                        days=Config.SUBSCRIPTION_DAYS
                    )
                except TypeError:
                    try:
                        await db_manager.create_token(token_str)
                    except Exception:
                        pass

            # Always store in memory as backup
            self._mem_tokens[token_str] = {
                "token": token_str,
                "chat_id": None,
                "created_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "expires_at": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "is_used": False,
                "activated_by": None,
            }

            print("[BOT] 🔑 Token created: {}****".format(
                token_str[:8]
            ))
            return token_str

        except Exception as e:
            print("[BOT] ❌ Token creation error: {}".format(e))
            return None

    async def _db_validate_token(self, token_str):
        """
        Validate a token string.

        Checks:
        1. Token exists
        2. Token not already used by another user
        3. Token not expired

        Args:
            token_str (str): The token to validate

        Returns:
            dict: {"valid": bool, "error": str or None,
                   "token_data": dict or None}
        """
        try:
            token_data = None

            # Check database first
            if DB_AVAILABLE and db_manager:
                try:
                    token_data = await db_manager.get_token(token_str)
                except Exception:
                    pass

            # Check memory fallback
            if not token_data:
                token_data = self._mem_tokens.get(token_str)

            if not token_data:
                return {
                    "valid": False,
                    "error": "Token not found. Please check "
                             "and try again.",
                    "token_data": None,
                }

            # Check if already used by another user
            activated_by = token_data.get(
                "activated_by",
                token_data.get("chat_id")
            )
            is_used = token_data.get("is_used", False)

            if is_used and activated_by:
                return {
                    "valid": False,
                    "error": "This token has already been "
                             "activated by another user.",
                    "token_data": None,
                }

            # Check expiry
            expires_str = token_data.get("expires_at", "")
            if expires_str:
                try:
                    if isinstance(expires_str, str):
                        expires = datetime.strptime(
                            expires_str, "%Y-%m-%d %H:%M:%S"
                        )
                    else:
                        expires = expires_str

                    if datetime.now() > expires:
                        return {
                            "valid": False,
                            "error": "This token has expired. "
                                     "Please purchase a new one.",
                            "token_data": None,
                        }
                except (ValueError, TypeError):
                    pass

            return {
                "valid": True,
                "error": None,
                "token_data": token_data,
            }

        except Exception as e:
            print("[BOT] ❌ Token validation error: {}".format(e))
            return {
                "valid": False,
                "error": "Validation error. Please try again.",
                "token_data": None,
            }

    async def _db_activate_token(self, token_str, chat_id):
        """
        Activate a token and create subscription.

        Locks the token to the user's chat_id and
        creates an active subscription with expiry.

        Args:
            token_str (str): Valid token string
            chat_id (int):   User's chat ID

        Returns:
            dict: {"success": bool, "expiry": str}
        """
        try:
            expiry = datetime.now() + timedelta(
                days=Config.SUBSCRIPTION_DAYS
            )
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S")

            # Activate in database
            if DB_AVAILABLE and db_manager:
                try:
                    await db_manager.activate_token(token_str, chat_id)
                except Exception as e:
                    print("[BOT] DB activate_token: {}".format(e))

            # Activate in memory
            if token_str in self._mem_tokens:
                self._mem_tokens[token_str]["is_used"] = True
                self._mem_tokens[token_str]["activated_by"] = chat_id

            # Create subscription record
            self._mem_subs[chat_id] = {
                "chat_id": chat_id,
                "token": token_str,
                "start_date": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "end_date": expiry_str,
                "is_active": True,
            }

            print("[BOT] ✅ Token activated for chat_id: {}".format(
                chat_id
            ))

            return {
                "success": True,
                "expiry": expiry_str,
            }

        except Exception as e:
            print("[BOT] ❌ Token activation error: {}".format(e))
            return {"success": False, "expiry": ""}

    async def _db_is_subscribed(self, chat_id):
        """
        Check if user has an active subscription.

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            bool: True if subscription is active
        """
        try:
            # Check database
            if DB_AVAILABLE and db_manager:
                try:
                    result = await db_manager.is_subscribed(chat_id)
                    if result:
                        return True
                except Exception:
                    pass

            # Check memory
            sub = self._mem_subs.get(chat_id)
            if sub and sub.get("is_active"):
                end_str = sub.get("end_date", "")
                if end_str:
                    try:
                        end_date = datetime.strptime(
                            end_str, "%Y-%m-%d %H:%M:%S"
                        )
                        if datetime.now() <= end_date:
                            return True
                        else:
                            sub["is_active"] = False
                            return False
                    except (ValueError, TypeError):
                        return True
                return True

            return False

        except Exception as e:
            print("[BOT] ❌ Subscription check error: {}".format(e))
            return False

    async def _db_get_subscription(self, chat_id):
        """
        Get subscription details for a user.

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            dict or None: Subscription data
        """
        try:
            # Check database
            if DB_AVAILABLE and db_manager:
                try:
                    sub = await db_manager.get_subscription(chat_id)
                    if sub:
                        return sub
                except Exception:
                    pass

            # Check memory
            return self._mem_subs.get(chat_id)

        except Exception as e:
            print("[BOT] ❌ Get subscription error: {}".format(e))
            return None

    async def _db_get_signal_count(self, chat_id):
        """
        Get total signals received by a user.

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            int: Number of signals received
        """
        try:
            if DB_AVAILABLE and db_manager:
                try:
                    count = await db_manager.get_signal_count(chat_id)
                    if count is not None:
                        return int(count)
                except Exception:
                    pass

            return self._mem_signals_count.get(chat_id, 0)

        except Exception:
            return 0

    async def _db_get_active_subscribers(self):
        """
        Get all chat IDs with active subscriptions.

        Returns:
            list[int]: List of active subscriber chat IDs
        """
        try:
            subscribers = []

            # From database
            if DB_AVAILABLE and db_manager:
                try:
                    db_subs = await db_manager.get_active_subscribers()
                    if db_subs:
                        subscribers.extend(db_subs)
                except Exception:
                    pass

            # From memory
            for chat_id, sub in self._mem_subs.items():
                if sub.get("is_active") and chat_id not in subscribers:
                    end_str = sub.get("end_date", "")
                    try:
                        end_date = datetime.strptime(
                            end_str, "%Y-%m-%d %H:%M:%S"
                        )
                        if datetime.now() <= end_date:
                            subscribers.append(chat_id)
                    except (ValueError, TypeError):
                        subscribers.append(chat_id)

            return subscribers

        except Exception as e:
            print("[BOT] ❌ Get subscribers error: {}".format(e))
            return []

    async def _db_increment_signal_count(self, chat_id):
        """Increment signal count for a user."""
        current = self._mem_signals_count.get(chat_id, 0)
        self._mem_signals_count[chat_id] = current + 1

    # ============================================
    # FUNCTION 3: /start COMMAND
    # ============================================

    async def start_command(self, update, context):
        """
        Handle /start command.

        Flow:
        1. Extract user info from update
        2. Register user in database (if new)
        3. Send welcome message with inline keyboard
        4. Log the interaction

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context
        """
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id
            username = user.username or ""
            first_name = user.first_name or "Trader"

            # Register user
            await self._db_add_user(chat_id, username, first_name)

            # Check subscription status
            is_active = await self._db_is_subscribed(chat_id)
            status_emoji = "✅ Active" if is_active else "❌ Inactive"

            welcome = (
                "🤖 <b>Welcome to CryptoSignal Bot!</b>\n"
                "\n"
                "📊 AI-powered crypto trading signals\n"
                "🎯 65%+ confidence signals only\n"
                "⏰ Real-time analysis every 10 minutes\n"
                "\n"
                "💎 <b>Premium Access: ₹{price} "
                "for {days} days</b>\n"
                "\n"
                "<b>What you get:</b>\n"
                "✅ Unlimited trading signals\n"
                "✅ All 10 major crypto pairs\n"
                "✅ Entry, Target, Stop Loss\n"
                "✅ AI confidence scoring\n"
                "✅ 24/7 market monitoring\n"
                "\n"
                "👤 <b>{name}</b> | "
                "Status: <b>{status}</b>\n"
                "\n"
                "Choose an option below 👇"
            ).format(
                price=Config.SUBSCRIPTION_PRICE,
                days=Config.SUBSCRIPTION_DAYS,
                name=first_name,
                status=status_emoji,
            )

            await update.message.reply_text(
                welcome,
                parse_mode=ParseMode.HTML,
                reply_markup=self._get_main_keyboard(),
            )

            print("[BOT] /start from {} (chat_id: {})".format(
                first_name, chat_id
            ))

        except Exception as e:
            print("[BOT] ❌ /start error: {}".format(e))
            await update.message.reply_text(
                "❌ Something went wrong. Please try /start again."
            )

    # ============================================
    # FUNCTION 4: /status COMMAND
    # ============================================

    async def status_command(self, update, context):
        """
        Handle /status command.

        Shows the user's subscription status, expiry,
        signals received, and membership info.

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context
        """
        try:
            chat_id = update.effective_chat.id
            user = update.effective_user
            first_name = user.first_name or "Trader"

            await self._send_status_message(
                update.message, chat_id, first_name
            )

        except Exception as e:
            print("[BOT] ❌ /status error: {}".format(e))
            await update.message.reply_text(
                "❌ Could not retrieve status. Try again."
            )

    async def _send_status_message(self, message_or_query,
                                    chat_id, first_name):
        """
        Build and send status message.

        Used by both /status command and My Status button.

        Args:
            message_or_query: Message or CallbackQuery object
            chat_id (int):    User's chat ID
            first_name (str): User's first name
        """
        try:
            is_active = await self._db_is_subscribed(chat_id)
            sub = await self._db_get_subscription(chat_id)
            signal_count = await self._db_get_signal_count(chat_id)
            user_data = await self._db_get_user(chat_id)

            # Subscription details
            if is_active and sub:
                status_line = "🔐 Subscription: <b>ACTIVE ✅</b>"

                end_str = sub.get("end_date", "N/A")
                try:
                    if isinstance(end_str, str):
                        end_date = datetime.strptime(
                            end_str, "%Y-%m-%d %H:%M:%S"
                        )
                    else:
                        end_date = end_str
                    days_left = (end_date - datetime.now()).days
                    days_left = max(0, days_left)
                    expiry_display = end_date.strftime("%d %b %Y")
                except (ValueError, TypeError):
                    days_left = "?"
                    expiry_display = str(end_str)

                token_str = sub.get("token", "")
                if len(token_str) >= 4:
                    token_display = token_str[-4:] + "****"
                else:
                    token_display = "****"

                sub_details = (
                    "📅 Expires: <b>{expiry}</b>\n"
                    "⏳ Days left: <b>{days}</b>\n"
                    "📈 Signals received: <b>{signals}</b>\n"
                    "🔑 Token: <code>{token}</code>"
                ).format(
                    expiry=expiry_display,
                    days=days_left,
                    signals=signal_count,
                    token=token_display,
                )
            else:
                status_line = "🔐 Subscription: <b>INACTIVE ❌</b>"
                sub_details = (
                    "📅 Expires: <b>N/A</b>\n"
                    "⏳ Days left: <b>0</b>\n"
                    "📈 Signals received: <b>{}</b>\n"
                    "\n"
                    "💡 <i>Click 'Get Premium' to start "
                    "receiving signals!</i>"
                ).format(signal_count)

            # Join date
            join_date = "N/A"
            if user_data:
                join_date = user_data.get(
                    "joined_at",
                    user_data.get("join_date", "N/A")
                )
                if isinstance(join_date, str) and len(join_date) > 10:
                    join_date = join_date[:10]

            status_msg = (
                "📊 <b>Your Status</b>\n"
                "\n"
                "👤 Name: <b>{name}</b>\n"
                "🆔 Chat ID: <code>{chat_id}</code>\n"
                "📅 Member since: <b>{joined}</b>\n"
                "\n"
                "{status}\n"
                "{details}"
            ).format(
                name=first_name,
                chat_id=chat_id,
                joined=join_date,
                status=status_line,
                details=sub_details,
            )

            back_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔙 Back to Menu",
                    callback_data="back_to_main"
                )]
            ])

            # Send or edit message
            if hasattr(message_or_query, 'edit_message_text'):
                await message_or_query.edit_message_text(
                    status_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=back_keyboard,
                )
            else:
                await message_or_query.reply_text(
                    status_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=back_keyboard,
                )

        except Exception as e:
            print("[BOT] ❌ Status message error: {}".format(e))
            error_msg = "❌ Could not retrieve status."
            if hasattr(message_or_query, 'edit_message_text'):
                await message_or_query.edit_message_text(error_msg)
            else:
                await message_or_query.reply_text(error_msg)

    # ============================================
    # FUNCTION 5: /help COMMAND
    # ============================================

    async def help_command(self, update, context):
        """
        Handle /help command.

        Shows all commands, how the bot works,
        and frequently asked questions.

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context
        """
        try:
            await self._send_help_message(update.message)

        except Exception as e:
            print("[BOT] ❌ /help error: {}".format(e))
            await update.message.reply_text(
                "❌ Could not load help. Try again."
            )

    async def _send_help_message(self, message_or_query):
        """
        Build and send help message.

        Args:
            message_or_query: Message or CallbackQuery object
        """
        help_text = (
            "ℹ️ <b>CryptoSignal Bot — Help Guide</b>\n"
            "\n"
            "━━━ <b>Commands</b> ━━━\n"
            "/start  — Main menu & registration\n"
            "/status — Check subscription status\n"
            "/help   — This help message\n"
            "/cancel — Cancel current operation\n"
            "\n"
            "━━━ <b>How It Works</b> ━━━\n"
            "1️⃣ Click <b>💰 Get Premium</b> to get a token\n"
            "2️⃣ Click <b>🔑 Activate Token</b> and paste it\n"
            "3️⃣ Receive AI signals automatically!\n"
            "\n"
            "━━━ <b>Signal Format</b> ━━━\n"
            "Each signal includes:\n"
            "• 🔷 Trading pair (e.g. BTC/USDT)\n"
            "• 📈 Direction (LONG or SHORT)\n"
            "• 🎯 Confidence score (65-100%)\n"
            "• 💰 Entry price\n"
            "• 🎯 Target price\n"
            "• 🛑 Stop loss\n"
            "\n"
            "━━━ <b>AI Analysis</b> ━━━\n"
            "Our bot uses <b>8 AI brains</b>:\n"
            "• RSI — Momentum\n"
            "• MACD — Trend direction\n"
            "• Bollinger Bands — Volatility\n"
            "• Volume Analysis — Activity\n"
            "• EMA Crossover — Trend strength\n"
            "• Support/Resistance — Key levels\n"
            "• Candlestick Patterns — Price action\n"
            "• OBV — Money flow\n"
            "\n"
            "━━━ <b>FAQ</b> ━━━\n"
            "<b>Q: How often are signals sent?</b>\n"
            "A: Every 10 minutes when opportunities "
            "arise (65%+ confidence)\n"
            "\n"
            "<b>Q: Which pairs are tracked?</b>\n"
            "A: Top 10 crypto pairs including BTC, "
            "ETH, BNB, SOL, XRP and more\n"
            "\n"
            "<b>Q: How long is the subscription?</b>\n"
            "A: {days} days from activation\n"
            "\n"
            "<b>Q: Is my token shareable?</b>\n"
            "A: No — each token is locked to one account\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <b>Disclaimer:</b> Crypto trading involves "
            "significant risk. Signals are for educational "
            "purposes. Only invest what you can afford to lose."
        ).format(days=Config.SUBSCRIPTION_DAYS)

        back_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔙 Back to Menu",
                callback_data="back_to_main"
            )]
        ])

        if hasattr(message_or_query, 'edit_message_text'):
            await message_or_query.edit_message_text(
                help_text,
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard,
            )
        else:
            await message_or_query.reply_text(
                help_text,
                parse_mode=ParseMode.HTML,
                reply_markup=back_keyboard,
            )

    # ============================================
    # FUNCTION 6: CALLBACK BUTTON HANDLER
    # ============================================

    async def button_handler(self, update, context):
        """
        Route inline keyboard button clicks.

        Handles all callback queries EXCEPT
        'activate_token' (which is handled by
        the ConversationHandler).

        Routing:
        - my_status    → show subscription status
        - get_premium  → generate token or payment
        - help         → show help guide
        - back_to_main → return to main menu

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context
        """
        try:
            query = update.callback_query
            await query.answer()

            data = query.data
            chat_id = update.effective_chat.id
            first_name = update.effective_user.first_name or "Trader"

            print("[BOT] Button: '{}' from {} (chat: {})".format(
                data, first_name, chat_id
            ))

            if data == "my_status":
                await self._send_status_message(
                    query, chat_id, first_name
                )

            elif data == "get_premium":
                await self._handle_get_premium(query, chat_id)

            elif data == "help":
                await self._send_help_message(query)

            elif data == "back_to_main":
                await self._send_main_menu(query, first_name)

            else:
                await query.edit_message_text(
                    "❓ Unknown action. Use /start to begin."
                )

        except Exception as e:
            print("[BOT] ❌ Button handler error: {}".format(e))
            try:
                await update.callback_query.edit_message_text(
                    "❌ Error processing action. Try /start again."
                )
            except Exception:
                pass

    async def _send_main_menu(self, query, first_name):
        """
        Send main menu (back to /start view).

        Args:
            query:          CallbackQuery object
            first_name:     User's first name
        """
        menu_msg = (
            "🤖 <b>CryptoSignal Bot</b>\n"
            "\n"
            "Welcome back, <b>{name}</b>!\n"
            "\n"
            "Choose an option below 👇"
        ).format(name=first_name)

        await query.edit_message_text(
            menu_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=self._get_main_keyboard(),
        )

    # ============================================
    # FUNCTION 7: GET PREMIUM HANDLER
    # ============================================

    async def _handle_get_premium(self, query, chat_id):
        """
        Handle 'Get Premium' button click.

        Behavior depends on PAYMENT_MODE:
        - "fake": Generate free test token immediately
        - "real": Show Razorpay payment link

        Args:
            query:      CallbackQuery object
            chat_id:    User's chat ID
        """
        try:
            if self.payment_mode.lower() == "fake":
                # ------ FAKE MODE: Generate free token ------
                token_str = await self._db_create_token(chat_id)

                if not token_str:
                    await query.edit_message_text(
                        "❌ Failed to generate token. Try again."
                    )
                    return

                msg = (
                    "🎁 <b>TEST MODE — Free Token Generated!</b>\n"
                    "\n"
                    "🔑 Your Token:\n"
                    "<code>{token}</code>\n"
                    "\n"
                    "📋 <i>Tap the token above to copy it</i>\n"
                    "\n"
                    "Then click <b>🔑 Activate Token</b> below "
                    "to start receiving signals.\n"
                    "\n"
                    "⚠️ <i>This is test mode. In production, "
                    "payment will be required.</i>"
                ).format(token=token_str)

                activate_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "🔑 Activate Token",
                        callback_data="activate_token"
                    )],
                    [InlineKeyboardButton(
                        "🔙 Back to Menu",
                        callback_data="back_to_main"
                    )],
                ])

                await query.edit_message_text(
                    msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=activate_keyboard,
                )

                print("[BOT] 🎁 Fake token issued to chat: {}".format(
                    chat_id
                ))

            else:
                # ------ REAL MODE: Show payment link ------
                razorpay_key = Config.RAZORPAY_KEY_ID

                if razorpay_key:
                    payment_url = (
                        "https://rzp.io/l/cryptosignal"
                    )
                else:
                    payment_url = "(Payment link not configured)"

                msg = (
                    "💰 <b>Premium Subscription</b>\n"
                    "\n"
                    "💎 Plan: <b>{days} Days Access</b>\n"
                    "💰 Price: <b>₹{price}</b>\n"
                    "\n"
                    "━━━ <b>What you get</b> ━━━\n"
                    "✅ Unlimited trading signals\n"
                    "✅ All 10 major crypto pairs\n"
                    "✅ Entry, Target, Stop Loss\n"
                    "✅ AI confidence scoring\n"
                    "✅ 24/7 market monitoring\n"
                    "\n"
                    "🔗 <b>Pay securely via Razorpay:</b>\n"
                    "{link}\n"
                    "\n"
                    "After payment, your token will be "
                    "sent automatically. Then click "
                    "<b>🔑 Activate Token</b> to enter it."
                ).format(
                    days=Config.SUBSCRIPTION_DAYS,
                    price=Config.SUBSCRIPTION_PRICE,
                    link=payment_url,
                )

                back_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "🔑 Activate Token",
                        callback_data="activate_token"
                    )],
                    [InlineKeyboardButton(
                        "🔙 Back to Menu",
                        callback_data="back_to_main"
                    )],
                ])

                await query.edit_message_text(
                    msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=back_keyboard,
                )

        except Exception as e:
            print("[BOT] ❌ Get Premium error: {}".format(e))
            await query.edit_message_text(
                "❌ Error processing request. Try /start again."
            )

    # ============================================
    # FUNCTION 8: TOKEN ACTIVATION CONVERSATION
    # ============================================

    async def ask_for_token(self, update, context):
        """
        ConversationHandler ENTRY POINT.

        Called when user clicks 'Activate Token'.
        Asks user to type/paste their token.

        Returns WAITING_FOR_TOKEN state.

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context

        Returns:
            int: WAITING_FOR_TOKEN state
        """
        try:
            query = update.callback_query
            await query.answer()

            msg = (
                "🔑 <b>Token Activation</b>\n"
                "\n"
                "Please enter your activation token below.\n"
                "\n"
                "📋 <i>Paste the full token (UUID format)</i>\n"
                "\n"
                "Type /cancel to abort."
            )

            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="cancel_activation"
                )]
            ])

            await query.edit_message_text(
                msg,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard,
            )

            print("[BOT] Waiting for token from chat: {}".format(
                update.effective_chat.id
            ))

            return WAITING_FOR_TOKEN

        except Exception as e:
            print("[BOT] ❌ ask_for_token error: {}".format(e))
            return ConversationHandler.END

    async def receive_token(self, update, context):
        """
        ConversationHandler STATE HANDLER.

        Called when user sends text while in
        WAITING_FOR_TOKEN state. Validates the token
        and activates subscription if valid.

        Flow:
        1. Extract token from message text
        2. Strip whitespace and normalize
        3. Validate token (exists, not used, not expired)
        4. If valid: activate and create subscription
        5. If invalid: show specific error
        6. End conversation

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context

        Returns:
            int: ConversationHandler.END
        """
        try:
            chat_id = update.effective_chat.id
            token_input = update.message.text.strip().upper()

            print("[BOT] Token received from {}: {}****".format(
                chat_id, token_input[:8] if len(token_input) >= 8
                else token_input
            ))

            # ------ Validate ------
            validation = await self._db_validate_token(token_input)

            if not validation["valid"]:
                error_msg = (
                    "❌ <b>Token Activation Failed</b>\n"
                    "\n"
                    "Reason: {reason}\n"
                    "\n"
                    "Please check your token and try again "
                    "using <b>🔑 Activate Token</b>."
                ).format(reason=validation["error"])

                back_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "🔑 Try Again",
                        callback_data="activate_token"
                    )],
                    [InlineKeyboardButton(
                        "💰 Get Premium",
                        callback_data="get_premium"
                    )],
                    [InlineKeyboardButton(
                        "🔙 Back to Menu",
                        callback_data="back_to_main"
                    )],
                ])

                await update.message.reply_text(
                    error_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=back_keyboard,
                )

                return ConversationHandler.END

            # ------ Activate ------
            result = await self._db_activate_token(token_input, chat_id)

            if result["success"]:
                success_msg = (
                    "✅ <b>Token Activated Successfully!</b>\n"
                    "\n"
                    "🔐 Your access is now <b>ACTIVE</b>\n"
                    "📅 Valid until: <b>{expiry}</b>\n"
                    "📈 Signals will start flowing!\n"
                    "\n"
                    "You will receive signals every "
                    "{interval} minutes for all qualifying "
                    "pairs ({min_conf}%+ confidence).\n"
                    "\n"
                    "🎉 <i>Happy trading!</i>"
                ).format(
                    expiry=result["expiry"][:10],
                    interval=Config.SIGNAL_INTERVAL_MINUTES,
                    min_conf=Config.MIN_CONFIDENCE,
                )

                menu_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "📊 My Status",
                        callback_data="my_status"
                    )],
                    [InlineKeyboardButton(
                        "🔙 Back to Menu",
                        callback_data="back_to_main"
                    )],
                ])

                await update.message.reply_text(
                    success_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=menu_keyboard,
                )

                print("[BOT] ✅ Subscription activated "
                      "for chat: {}".format(chat_id))

            else:
                await update.message.reply_text(
                    "❌ Activation failed. Please contact "
                    "support or try again.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "🔙 Back to Menu",
                            callback_data="back_to_main"
                        )]
                    ]),
                )

            return ConversationHandler.END

        except Exception as e:
            print("[BOT] ❌ receive_token error: {}".format(e))
            await update.message.reply_text(
                "❌ Error processing token. Try /start again."
            )
            return ConversationHandler.END

    async def cancel_activation(self, update, context):
        """
        Cancel the token activation conversation.

        Called by /cancel command or cancel button
        during WAITING_FOR_TOKEN state.

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context

        Returns:
            int: ConversationHandler.END
        """
        try:
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    "❌ Token activation cancelled.\n\n"
                    "Use /start to return to the main menu.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "🔙 Back to Menu",
                            callback_data="back_to_main"
                        )]
                    ]),
                )
            elif update.message:
                await update.message.reply_text(
                    "❌ Token activation cancelled.\n\n"
                    "Use /start to return to the main menu.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "🔙 Back to Menu",
                            callback_data="back_to_main"
                        )]
                    ]),
                )

            return ConversationHandler.END

        except Exception as e:
            print("[BOT] ❌ cancel error: {}".format(e))
            return ConversationHandler.END

    async def conversation_timeout(self, update, context):
        """
        Handle conversation timeout.

        Sent when user doesn't input a token within
        the timeout period (120 seconds).

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context
        """
        try:
            chat_id = update.effective_chat.id
            if self.application and self.application.bot:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "⏰ Token activation timed out.\n\n"
                        "Click 🔑 <b>Activate Token</b> "
                        "to try again."
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "🔑 Activate Token",
                            callback_data="activate_token"
                        )],
                        [InlineKeyboardButton(
                            "🔙 Back to Menu",
                            callback_data="back_to_main"
                        )],
                    ]),
                )
        except Exception as e:
            print("[BOT] Timeout handler error: {}".format(e))

    async def button_during_conversation(self, update, context):
        """
        Handle button clicks during token activation.

        If user clicks any button while waiting for
        token input, end the conversation and route
        to the appropriate handler.

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context

        Returns:
            int: ConversationHandler.END
        """
        try:
            data = update.callback_query.data

            if data == "cancel_activation":
                return await self.cancel_activation(update, context)

            # Route to main button handler and end conversation
            await self.button_handler(update, context)
            return ConversationHandler.END

        except Exception as e:
            print("[BOT] ❌ Conv button error: {}".format(e))
            return ConversationHandler.END

    # ============================================
    # FUNCTION 9: AUTHORIZATION CHECK
    # ============================================

    async def is_user_authorized(self, chat_id):
        """
        Quick check if user has active subscription.

        Used by signal engine before sending signals.

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            bool: True if subscription active
        """
        return await self._db_is_subscribed(chat_id)

    async def send_unauthorized_message(self, chat_id):
        """
        Send subscription required message.

        Called when unauthorized user tries to
        access premium features.

        Args:
            chat_id (int): Telegram chat ID
        """
        try:
            if not self.application or not self.application.bot:
                return

            msg = (
                "🔒 <b>Premium Access Required</b>\n"
                "\n"
                "This feature requires an active "
                "subscription.\n"
                "\n"
                "💎 Get {days} days of premium signals "
                "for just ₹{price}!\n"
                "\n"
                "Click below to get started 👇"
            ).format(
                days=Config.SUBSCRIPTION_DAYS,
                price=Config.SUBSCRIPTION_PRICE,
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "💰 Get Premium",
                    callback_data="get_premium"
                )],
                [InlineKeyboardButton(
                    "🔑 Activate Token",
                    callback_data="activate_token"
                )],
            ])

            await self.application.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

        except Exception as e:
            print("[BOT] ❌ Unauthorized msg error: {}".format(e))

    # ============================================
    # FUNCTION 10: SIGNAL FORMATTING
    # ============================================

    def format_signal_message(self, signal_data):
        """
        Format a trading signal into a beautiful
        Telegram message using HTML.

        Signal data expected format:
        {
            "pair": "BTC/USDT",
            "direction": "LONG",
            "confidence": 78.5,
            "entry_price": 67500.0,
            "target_price": 69000.0,
            "stop_loss": 66500.0,
            "timeframe": "5m",
            "brains": {...},
            "timestamp": "2024-01-15 10:30:00"
        }

        Args:
            signal_data (dict): Signal information

        Returns:
            str: Formatted HTML message
        """
        try:
            pair = signal_data.get("pair", "???/USDT")
            direction = signal_data.get("direction", "NEUTRAL")
            confidence = signal_data.get("confidence", 0)
            entry = signal_data.get("entry_price", 0)
            target = signal_data.get("target_price", 0)
            stop = signal_data.get("stop_loss", 0)
            timeframe = signal_data.get("timeframe", "5m")
            timestamp = signal_data.get(
                "timestamp",
                datetime.now().strftime("%Y-%m-%d %H:%M UTC")
            )

            # Direction emoji and text
            if direction == "LONG":
                dir_emoji = "📈"
                dir_text = "LONG ✅"
                dir_color = "🟢"
            elif direction == "SHORT":
                dir_emoji = "📉"
                dir_text = "SHORT 🔻"
                dir_color = "🔴"
            else:
                dir_emoji = "⏸"
                dir_text = "NEUTRAL"
                dir_color = "⚪"

            # Calculate percentages
            if entry and entry > 0:
                if target:
                    target_pct = ((target - entry) / entry) * 100
                    target_pct_str = "{:+.2f}%".format(target_pct)
                else:
                    target_pct_str = "N/A"

                if stop:
                    stop_pct = ((stop - entry) / entry) * 100
                    stop_pct_str = "{:+.2f}%".format(stop_pct)
                else:
                    stop_pct_str = "N/A"
            else:
                target_pct_str = "N/A"
                stop_pct_str = "N/A"

            # Format prices
            if entry >= 1000:
                entry_str = "${:,.2f}".format(entry)
                target_str = "${:,.2f}".format(target) if target else "N/A"
                stop_str = "${:,.2f}".format(stop) if stop else "N/A"
            elif entry >= 1:
                entry_str = "${:.4f}".format(entry)
                target_str = "${:.4f}".format(target) if target else "N/A"
                stop_str = "${:.4f}".format(stop) if stop else "N/A"
            else:
                entry_str = "${:.6f}".format(entry)
                target_str = "${:.6f}".format(target) if target else "N/A"
                stop_str = "${:.6f}".format(stop) if stop else "N/A"

            # Brain analysis section
            brains = signal_data.get("brains", {})
            brain_lines = []

            brain_order = [
                ("RSI", "RSI"),
                ("MACD", "MACD"),
                ("BOLLINGER", "Bollinger"),
                ("VOLUME", "Volume"),
                ("EMA", "EMA"),
                ("SUPPORT_RESISTANCE", "S/R"),
                ("CANDLE_PATTERNS", "Candles"),
                ("OBV", "OBV"),
            ]

            for brain_key, brain_name in brain_order:
                brain_data = brains.get(brain_key, {})
                if brain_data:
                    b_dir = brain_data.get("direction", "?")
                    b_conf = brain_data.get("confidence", 0)

                    if b_dir == "LONG":
                        b_emoji = "🟢"
                    elif b_dir == "SHORT":
                        b_emoji = "🔴"
                    else:
                        b_emoji = "⚪"

                    brain_lines.append(
                        "  {} {} — {} ({}%)".format(
                            b_emoji, brain_name, b_dir, b_conf
                        )
                    )

            if brain_lines:
                brain_section = "\n".join(brain_lines)
            else:
                brain_section = "  (analysis details not available)"

            # Confidence bar
            filled = int(confidence / 10)
            empty = 10 - filled
            conf_bar = "█" * filled + "░" * empty

            # Build message
            msg = (
                "{dir_color}  <b>CRYPTO SIGNAL ALERT</b>  {dir_color}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "🔷 Pair: <b>{pair}</b>\n"
                "{dir_emoji} Direction: <b>{dir_text}</b>\n"
                "🎯 Confidence: <b>{conf:.1f}%</b>\n"
                "   [{conf_bar}]\n"
                "\n"
                "━━━ Trade Setup ━━━\n"
                "💰 Entry:  <code>{entry}</code>\n"
                "🎯 Target: <code>{target}</code> "
                "({target_pct})\n"
                "🛑 Stop:   <code>{stop}</code> "
                "({stop_pct})\n"
                "\n"
                "━━━ AI Brain Analysis ━━━\n"
                "{brains}\n"
                "\n"
                "⏰ {time} | 📊 {tf}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ <i>Not financial advice. "
                "Trade at your own risk.</i>"
            ).format(
                dir_color=dir_color,
                pair=pair,
                dir_emoji=dir_emoji,
                dir_text=dir_text,
                conf=confidence,
                conf_bar=conf_bar,
                entry=entry_str,
                target=target_str,
                target_pct=target_pct_str,
                stop=stop_str,
                stop_pct=stop_pct_str,
                brains=brain_section,
                time=timestamp,
                tf=timeframe,
            )

            return msg

        except Exception as e:
            print("[BOT] ❌ Format signal error: {}".format(e))
            return (
                "📊 <b>Signal Alert</b>\n\n"
                "Pair: {}\n"
                "Direction: {}\n"
                "Confidence: {}%\n"
                "\n"
                "(Full details unavailable)"
            ).format(
                signal_data.get("pair", "?"),
                signal_data.get("direction", "?"),
                signal_data.get("confidence", 0),
            )

    # ============================================
    # FUNCTION 11: SEND SIGNAL TO USER
    # ============================================

    async def send_signal_to_user(self, chat_id, signal_data):
        """
        Send a trading signal to a single user.

        Args:
            chat_id (int):        Target user's chat ID
            signal_data (dict):   Signal information

        Returns:
            bool: True if sent successfully
        """
        try:
            if not self.application or not self.application.bot:
                print("[BOT] ❌ Application not ready")
                return False

            message = self.format_signal_message(signal_data)

            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )

            await self._db_increment_signal_count(chat_id)

            print("[BOT] 📨 Signal sent to {}".format(chat_id))
            return True

        except Exception as e:
            print("[BOT] ❌ Send to user {} error: {}".format(
                chat_id, e
            ))
            return False

    # ============================================
    # FUNCTION 12: BROADCAST TO SUBSCRIBERS
    # ============================================

    async def broadcast_signal(self, signal_data):
        """
        Send a signal to ALL active subscribers.

        Gets list of active subscribers from database,
        sends signal to each. Handles blocked/deleted
        users gracefully.

        Args:
            signal_data (dict): Signal information

        Returns:
            dict: {"sent": int, "failed": int, "total": int}
        """
        sent = 0
        failed_count = 0

        try:
            subscribers = await self._db_get_active_subscribers()
            total = len(subscribers)

            if total == 0:
                print("[BOT] No active subscribers")
                return {"sent": 0, "failed": 0, "total": 0}

            print("[BOT] 📡 Broadcasting signal to {} "
                  "subscribers...".format(total))

            message = self.format_signal_message(signal_data)

            for chat_id in subscribers:
                try:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                    )
                    await self._db_increment_signal_count(chat_id)
                    sent += 1

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.05)

                except Exception as e:
                    failed_count += 1
                    print("[BOT] ⚠️ Failed to send to {}: {}".format(
                        chat_id, e
                    ))

            print("[BOT] 📡 Broadcast complete: {}/{} sent, "
                  "{} failed".format(sent, total, failed_count))

            return {
                "sent": sent,
                "failed": failed_count,
                "total": total,
            }

        except Exception as e:
            print("[BOT] ❌ Broadcast error: {}".format(e))
            return {
                "sent": sent,
                "failed": failed_count,
                "total": 0,
            }

    # ============================================
    # FUNCTION 13: SEND TO PUBLIC CHANNEL
    # ============================================

    async def send_to_channel(self, signal_data):
        """
        Post a signal to the public Telegram channel.

        Uses TELEGRAM_PUBLIC_CHANNEL_ID from config.
        Skips if channel ID is not set.

        Public channel signals include a subscription
        call-to-action at the bottom.

        Args:
            signal_data (dict): Signal information

        Returns:
            bool: True if sent, False if skipped/error
        """
        try:
            if not self.channel_id:
                print("[BOT] ⚠️ No channel ID configured, "
                      "skipping channel post")
                return False

            if not self.application or not self.application.bot:
                print("[BOT] ❌ Application not ready")
                return False

            message = self.format_signal_message(signal_data)

            # Add channel CTA footer
            channel_footer = (
                "\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🤖 <b>Want all signals?</b>\n"
                "💎 Premium: ₹{price}/{days} days\n"
                "👉 DM @{bot} to subscribe!"
            ).format(
                price=Config.SUBSCRIPTION_PRICE,
                days=Config.SUBSCRIPTION_DAYS,
                bot=self.application.bot.username
                    if self.application.bot.username
                    else "CryptoSignalBot",
            )

            full_message = message + channel_footer

            await self.application.bot.send_message(
                chat_id=self.channel_id,
                text=full_message,
                parse_mode=ParseMode.HTML,
            )

            print("[BOT] 📢 Signal posted to channel")
            return True

        except Exception as e:
            print("[BOT] ❌ Channel post error: {}".format(e))
            return False

    # ============================================
    # FUNCTION 14: ERROR HANDLER
    # ============================================

    async def error_handler(self, update, context):
        """
        Global error handler for all bot errors.

        Logs the error and sends a friendly message
        to the user. Never exposes internal errors.

        Args:
            update (Update):           Telegram update
            context (ContextTypes):    Bot context
        """
        error = context.error

        print("[BOT] ❌ UNHANDLED ERROR: {}".format(error))
        logger.error(
            "Bot error: {}".format(error),
            exc_info=context.error,
        )

        try:
            if update and update.effective_chat:
                error_msg = (
                    "⚠️ Something went wrong.\n\n"
                    "Please try again or use /start "
                    "to restart."
                )

                if update.callback_query:
                    await update.callback_query.answer(
                        "An error occurred", show_alert=True
                    )
                    try:
                        await update.callback_query.edit_message_text(
                            error_msg
                        )
                    except Exception:
                        pass

                elif update.message:
                    await update.message.reply_text(error_msg)

        except Exception as e:
            print("[BOT] ❌ Error in error handler: {}".format(e))

    # ============================================
    # FUNCTION 15: BUILD APPLICATION
    # ============================================

    def build_application(self):
        """
        Build the telegram-bot Application with all
        handlers registered.

        Handler registration order:
        1. ConversationHandler (token activation)
        2. Command handlers (/start, /status, /help)
        3. General CallbackQueryHandler
        4. Error handler

        ConversationHandler is registered first so it
        takes priority for the 'activate_token' callback.

        Returns:
            Application: Configured application object
        """
        print("[BOT] Building application...")

        if not self.token:
            print("[BOT] ❌ Cannot build — no bot token!")
            return None

        # Build application
        app = Application.builder().token(self.token).build()

        # ---- 1. ConversationHandler (token flow) ----
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.ask_for_token,
                    pattern="^activate_token$"
                ),
            ],
            states={
                WAITING_FOR_TOKEN: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.receive_token
                    ),
                ],
                ConversationHandler.TIMEOUT: [
                    MessageHandler(
                        filters.ALL,
                        self.conversation_timeout
                    ),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_activation),
                CommandHandler("start", self.start_command),
                CallbackQueryHandler(
                    self.button_during_conversation
                ),
            ],
            conversation_timeout=120,
            per_message=False,
        )
        app.add_handler(conv_handler)

        # ---- 2. Command handlers ----
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("cancel", self.cancel_activation))

        # ---- 3. General callback handler ----
        app.add_handler(CallbackQueryHandler(self.button_handler))

        # ---- 4. Error handler ----
        app.add_error_handler(self.error_handler)

        self.application = app

        print("[BOT] ✅ Application built with {} handler(s)".format(
            len(app.handlers.get(0, []))
        ))

        return app

    # ============================================
    # FUNCTION 16: RUN
    # ============================================

    def run(self):
        """
        Build and start the bot with polling.

        Drops pending updates on start to avoid
        processing old messages.

        This method blocks until the bot is stopped
        (Ctrl+C or SIGINT).
        """
        app = self.build_application()

        if not app:
            print("[BOT] ❌ Cannot start — build failed!")
            return

        print("\n" + "=" * 50)
        print("  🤖 CRYPTO SIGNAL BOT — STARTING")
        print("  📡 Polling for updates...")
        print("  🛑 Press Ctrl+C to stop")
        print("=" * 50 + "\n")

        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

crypto_bot = CryptoSignalBot()

print("[BOT] ✅ Telegram bot module loaded and ready")