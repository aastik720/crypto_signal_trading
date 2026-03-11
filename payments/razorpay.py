"""
CryptoSignal Bot - Phase 11
Razorpay Payment Processing

THIS FILE ONLY HANDLES:
  - Razorpay API calls (create link, check status, verify)
  - Payment polling (every 30s check if paid)
  - Payment database records
  - Sending messages after payment

THIS FILE DOES NOT:
  - Generate tokens          → auth.py does that
  - Validate tokens          → auth.py does that
  - Activate subscriptions   → auth.py does that
  - Check authorization      → auth.py does that
  - Handle anti-sharing      → auth.py does that

When payment succeeds, this file calls:
  auth_manager.create_subscription(chat_id, payment_id)
That's it. auth.py handles all the security.

Modes:
  USE_RAZORPAY=false  →  Fake mode (admin gives tokens manually)
  USE_RAZORPAY=true   →  Real Razorpay payment links
"""

import os
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("payments")

# ─────────────────────────────────────────
# Try importing razorpay SDK
# ─────────────────────────────────────────
try:
    import razorpay
    RAZORPAY_SDK_AVAILABLE = True
except ImportError:
    RAZORPAY_SDK_AVAILABLE = False
    logger.warning(
        "razorpay SDK not installed. "
        "Run: pip install razorpay"
    )

# ─────────────────────────────────────────
# Import settings
# ─────────────────────────────────────────
from config.settings import Config

# ─────────────────────────────────────────
# Import auth manager (THE source of truth
# for tokens and subscriptions)
# ─────────────────────────────────────────
from security.auth import auth_manager

# ─────────────────────────────────────────
# Import database
# ─────────────────────────────────────────
try:
    from database.db_manager import db_manager
    DB_AVAILABLE = True
except ImportError:
    db_manager = None
    DB_AVAILABLE = False


class PaymentError(Exception):
    """Custom exception for payment errors."""
    pass


class PaymentManager:
    """
    Handles Razorpay payment processing ONLY.

    Does NOT manage tokens or subscriptions.
    Calls auth_manager for all security operations.

    Attributes:
        client:              Razorpay SDK client
        use_razorpay:        True = real payments, False = fake mode
        price_paise:         Price in paise (99900 = ₹999)
        price_inr:           Price in rupees (999)
        currency:            "INR"
        _active_polls:       Tracks ongoing payment polls
        _payment_records:    In-memory payment records (fallback)
    """

    # ─────────────────────────────────────
    # Constants
    # ─────────────────────────────────────
    POLL_INTERVAL = 30           # seconds between checks
    POLL_MAX_DURATION = 1800     # 30 minutes max polling
    LINK_EXPIRY_MINUTES = 35     # payment link expires

    def __init__(self):
        """
        Initialize PaymentManager.

        Reads config from Config class.
        Initializes Razorpay client only if USE_RAZORPAY=true.
        """
        # ── Read config ──
        try:
            self.use_razorpay = getattr(
                Config, "USE_RAZORPAY", False
            )
        except Exception:
            self.use_razorpay = False

        try:
            self.price_inr = int(getattr(
                Config, "SUBSCRIPTION_PRICE", 999
            ))
        except (ValueError, TypeError, AttributeError):
            self.price_inr = 999

        self.price_paise = self.price_inr * 100
        self.currency = "INR"

        try:
            self.sub_days = int(getattr(
                Config, "SUBSCRIPTION_DAYS", 28
            ))
        except (ValueError, TypeError, AttributeError):
            self.sub_days = 28

        try:
            self.admin_ids = Config.ADMIN_IDS
        except AttributeError:
            self.admin_ids = []

        try:
            self.channel_link = getattr(
                Config, "PRIVATE_CHANNEL_LINK", ""
            )
        except AttributeError:
            self.channel_link = ""

        # ── Razorpay client ──
        self.client = None

        # ── Tracking ──
        self._active_polls = {}        # {chat_id: True/False}
        self._payment_records = {}     # {order_id: record_dict}

        # ── Initialize ──
        if self.use_razorpay:
            self._init_razorpay()
        else:
            print("[PAYMENT] 💳 Running in FAKE mode "
                  "(USE_RAZORPAY=false)")
            print("[PAYMENT]    Tokens managed by auth.py")
            print("[PAYMENT]    Admin uses /gentoken command")

    # ═════════════════════════════════════
    #  RAZORPAY INITIALIZATION
    # ═════════════════════════════════════

    def _init_razorpay(self):
        """Initialize Razorpay SDK client."""
        if not RAZORPAY_SDK_AVAILABLE:
            raise PaymentError(
                "razorpay SDK not installed. "
                "Run: pip install razorpay"
            )

        try:
            key_id = getattr(Config, "RAZORPAY_KEY_ID", "")
            key_secret = getattr(Config, "RAZORPAY_KEY_SECRET", "")
        except AttributeError:
            key_id = ""
            key_secret = ""

        if not key_id or not key_secret:
            raise PaymentError(
                "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET "
                "must be set in .env"
            )

        try:
            self.client = razorpay.Client(
                auth=(key_id, key_secret)
            )
            print("[PAYMENT] 💳 Razorpay client initialized")
            print("[PAYMENT]    Key: {}...".format(key_id[:12]))
            print("[PAYMENT]    Price: ₹{}".format(self.price_inr))
        except Exception as e:
            raise PaymentError(
                "Razorpay init failed: {}".format(e)
            )

    # ═════════════════════════════════════
    #  CREATE PAYMENT LINK
    # ═════════════════════════════════════

    async def create_payment_link(
        self, chat_id, username=""
    ):
        """
        Create a Razorpay payment link for the user.

        In fake mode: returns instructions to contact admin.
        In real mode: creates actual Razorpay payment link.

        Before creating link, checks with auth_manager
        if user already has active subscription.

        Args:
            chat_id (int):    User's Telegram chat ID
            username (str):   User's Telegram username

        Returns:
            dict: {
                "success": bool,
                "message": str,
                "payment_url": str or None,
                "order_id": str or None
            }
        """
        try:
            # ── Check if already subscribed (ask auth.py) ──
            is_active = await auth_manager.is_authorized(chat_id)
            if is_active:
                sub_info = await auth_manager.get_subscription_info(
                    chat_id
                )
                end_date = sub_info.get("end_date", "N/A")
                days_left = sub_info.get("days_remaining", 0)

                return {
                    "success": False,
                    "message": (
                        "⚠️ You already have an active "
                        "subscription!\n\n"
                        "📅 Expires: {}\n"
                        "⏳ Days left: {}\n\n"
                        "No need to pay again.".format(
                            end_date, days_left
                        )
                    ),
                    "payment_url": None,
                    "order_id": None,
                }

            # ── Fake mode ──
            if not self.use_razorpay:
                return self._fake_payment_response(
                    chat_id, username
                )

            # ── Check for existing pending payment ──
            pending = self._get_pending_payment(chat_id)
            if pending:
                url = pending.get("payment_url", "")
                if url:
                    created = pending.get("created_at", "")
                    if created:
                        try:
                            created_dt = datetime.fromisoformat(
                                created
                            )
                            elapsed = (
                                datetime.now() - created_dt
                            ).total_seconds()
                            if elapsed < self.LINK_EXPIRY_MINUTES * 60:
                                return {
                                    "success": True,
                                    "message": (
                                        "You already have a pending "
                                        "payment link.\n\n"
                                        "Click below to complete "
                                        "payment:"
                                    ),
                                    "payment_url": url,
                                    "order_id": pending.get(
                                        "order_id"
                                    ),
                                }
                        except (ValueError, TypeError):
                            pass

            # ── Create real Razorpay link ──
            return await self._create_razorpay_link(
                chat_id, username
            )

        except Exception as e:
            logger.error(
                "Payment link error for {}: {}".format(
                    chat_id, e
                ),
                exc_info=True,
            )
            return {
                "success": False,
                "message": "❌ Payment system error. "
                           "Please try again later.",
                "payment_url": None,
                "order_id": None,
            }

    async def _create_razorpay_link(self, chat_id, username):
        """
        Actually call Razorpay API to create payment link.

        Args:
            chat_id (int):   User chat ID
            username (str):  Username for display

        Returns:
            dict with success, message, payment_url, order_id
        """
        if not self.client:
            return {
                "success": False,
                "message": "Payment system not configured.",
                "payment_url": None,
                "order_id": None,
            }

        display_name = username or "User_{}".format(chat_id)
        receipt = "order_{}_{}".format(chat_id, int(time.time()))

        payment_link_data = {
            "amount": self.price_paise,
            "currency": self.currency,
            "description": (
                "CryptoSignal Bot - "
                "{} Days Premium".format(self.sub_days)
            ),
            "customer": {
                "name": display_name,
                "contact": "",
                "email": "",
            },
            "notify": {
                "sms": False,
                "email": False,
            },
            "reminder_enable": False,
            "notes": {
                "chat_id": str(chat_id),
                "username": display_name,
                "plan": "{}_days_premium".format(self.sub_days),
                "receipt": receipt,
            },
            "callback_url": "",
            "callback_method": "get",
            "expire_by": int(time.time()) + (
                self.LINK_EXPIRY_MINUTES * 60
            ),
        }

        logger.info(
            "Creating Razorpay link: chat_id={}, "
            "amount={}".format(chat_id, self.price_paise)
        )

        try:
            response = self.client.payment_link.create(
                payment_link_data
            )
        except Exception as e:
            logger.error("Razorpay API error: {}".format(e))
            return {
                "success": False,
                "message": "❌ Could not create payment link. "
                           "Try again later.",
                "payment_url": None,
                "order_id": None,
            }

        payment_url = response.get("short_url", "")
        order_id = response.get("id", "")

        if not payment_url:
            logger.error(
                "Razorpay returned no URL: {}".format(response)
            )
            return {
                "success": False,
                "message": "❌ Payment link creation failed.",
                "payment_url": None,
                "order_id": None,
            }

        # ── Save payment record ──
        self._save_payment_record(
            chat_id=chat_id,
            order_id=order_id,
            payment_url=payment_url,
            receipt=receipt,
            status="created",
        )

        logger.info(
            "✅ Payment link created: {} for chat:{}".format(
                order_id, chat_id
            )
        )

        return {
            "success": True,
            "message": (
                "💳 Payment Link Created!\n\n"
                "💰 Amount: ₹{}\n"
                "📅 Plan: {} Days Premium\n\n"
                "Click the link below to pay:".format(
                    self.price_inr, self.sub_days
                )
            ),
            "payment_url": payment_url,
            "order_id": order_id,
        }

    def _fake_payment_response(self, chat_id, username):
        """
        Fake mode response — tells user to get token from admin.

        Returns:
            dict with instructions
        """
        logger.info(
            "Fake payment request from chat:{}".format(chat_id)
        )

        return {
            "success": True,
            "message": (
                "💳 Subscription Details\n\n"
                "💰 Price: ₹{}\n"
                "📅 Duration: {} days\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🔧 Payment system is in test mode.\n\n"
                "To get access:\n"
                "1️⃣ Contact the admin\n"
                "2️⃣ Complete payment manually\n"
                "3️⃣ Admin will give you a token\n"
                "4️⃣ Use /redeem YOUR-TOKEN\n\n"
                "Example:\n"
                "/redeem CSB-A1B2C3D4-XXXX".format(
                    self.price_inr, self.sub_days
                )
            ),
            "payment_url": None,
            "order_id": None,
        }

    # ═════════════════════════════════════
    #  PAYMENT STATUS CHECK
    # ═════════════════════════════════════

    async def check_payment_status(self, order_id):
        """
        Check payment status from Razorpay API.

        Args:
            order_id (str): Payment link ID (plink_XXXX)

        Returns:
            dict: {
                "status": "created" | "paid" | "expired"
                          | "cancelled" | "error",
                "payment_id": str or None
            }
        """
        if not self.client:
            return {"status": "error", "payment_id": None}

        try:
            response = self.client.payment_link.fetch(order_id)
            status = response.get("status", "unknown")
            payment_id = None

            if status == "paid":
                payments = response.get("payments", [])
                if isinstance(payments, list):
                    for p in payments:
                        if p.get("status") == "captured":
                            payment_id = p.get("payment_id")
                            break

            return {
                "status": status,
                "payment_id": payment_id,
            }

        except Exception as e:
            logger.error(
                "Status check error for {}: {}".format(
                    order_id, e
                )
            )
            return {"status": "error", "payment_id": None}

    # ═════════════════════════════════════
    #  PAYMENT POLLING
    # ═════════════════════════════════════

    async def poll_payment(
        self, chat_id, order_id, send_message=None
    ):
        """
        Poll Razorpay every 30s until payment is
        detected or timeout.

        When payment is detected:
        1. Calls auth_manager.create_subscription()
           (auth.py generates token, locks it, activates sub)
        2. Sends success message to user
        3. Notifies admin

        This file does NOT generate tokens or activate
        subscriptions. It ONLY detects payment and tells
        auth.py to do the security work.

        Args:
            chat_id (int):       User's chat ID
            order_id (str):      Razorpay payment link ID
            send_message:        async func(chat_id, text)
        """
        if not self.use_razorpay:
            logger.info(
                "Poll skipped (fake mode) for {}".format(chat_id)
            )
            return

        # Prevent duplicate polls
        if self._active_polls.get(chat_id):
            logger.warning(
                "Poll already active for {}".format(chat_id)
            )
            return

        self._active_polls[chat_id] = True
        start_time = time.time()
        poll_count = 0

        logger.info(
            "🔄 Poll started: chat={}, order={}".format(
                chat_id, order_id
            )
        )

        try:
            while self._active_polls.get(chat_id, False):
                elapsed = time.time() - start_time
                poll_count += 1

                # ── Timeout ──
                if elapsed >= self.POLL_MAX_DURATION:
                    logger.info(
                        "⏰ Poll timeout for {} after {}s".format(
                            chat_id, int(elapsed)
                        )
                    )

                    self._update_payment_status(
                        order_id, "poll_timeout"
                    )

                    if send_message:
                        await send_message(
                            chat_id,
                            "⏰ Payment check timed out.\n\n"
                            "If you already paid, please "
                            "contact support with your "
                            "payment ID.\n\n"
                            "Use /subscribe for a new link."
                        )
                    break

                # ── Check status ──
                result = await self.check_payment_status(
                    order_id
                )
                status = result["status"]

                # ── PAID → Tell auth.py to activate ──
                if status == "paid":
                    payment_id = result.get(
                        "payment_id", "rzp_{}".format(
                            int(time.time())
                        )
                    )

                    logger.info(
                        "💰 Payment confirmed! chat={}, "
                        "payment={}".format(
                            chat_id, payment_id
                        )
                    )

                    await self._handle_successful_payment(
                        chat_id=chat_id,
                        payment_id=payment_id,
                        order_id=order_id,
                        send_message=send_message,
                    )
                    break

                # ── EXPIRED / CANCELLED ──
                elif status in ("expired", "cancelled"):
                    logger.info(
                        "Payment {} for {}".format(
                            status, chat_id
                        )
                    )

                    self._update_payment_status(
                        order_id, status
                    )

                    if send_message:
                        if status == "expired":
                            msg = (
                                "⏰ Payment link expired.\n\n"
                                "Use /subscribe for a new link."
                            )
                        else:
                            msg = (
                                "❌ Payment cancelled.\n\n"
                                "Use /subscribe to try again."
                            )
                        await send_message(chat_id, msg)
                    break

                # ── Still waiting ──
                await asyncio.sleep(self.POLL_INTERVAL)

        except asyncio.CancelledError:
            logger.info(
                "Poll cancelled for {}".format(chat_id)
            )
        except Exception as e:
            logger.error(
                "Poll error for {}: {}".format(chat_id, e),
                exc_info=True,
            )
        finally:
            self._active_polls.pop(chat_id, None)
            logger.info(
                "Poll ended for {} ({} checks, {}s)".format(
                    chat_id, poll_count,
                    int(time.time() - start_time)
                )
            )

    def cancel_poll(self, chat_id):
        """Stop active poll for a user."""
        self._active_polls[chat_id] = False

    # ═════════════════════════════════════
    #  SUCCESSFUL PAYMENT → CALL AUTH.PY
    # ═════════════════════════════════════

    async def _handle_successful_payment(
        self, chat_id, payment_id, order_id,
        send_message=None
    ):
        """
        Payment confirmed by Razorpay. Now:
        1. Call auth_manager.create_subscription()
           → auth.py generates token
           → auth.py locks token to chat_id
           → auth.py activates subscription
           → auth.py logs everything
        2. Send success message to user
        3. Notify admin
        4. Update payment record

        THIS FILE DOES NOT TOUCH TOKENS OR SUBSCRIPTIONS.
        It only calls auth_manager and sends messages.

        Args:
            chat_id (int):     User's chat ID
            payment_id (str):  Razorpay payment ID
            order_id (str):    Razorpay order/link ID
            send_message:      async func(chat_id, text)
        """
        try:
            # ── Prevent duplicate processing ──
            record = self._get_payment_record(order_id)
            if record and record.get("status") == "completed":
                logger.warning(
                    "Payment {} already processed".format(
                        order_id
                    )
                )
                return

            # ═══════════════════════════════════
            # THIS IS THE KEY LINE
            # auth.py does ALL the security work
            # ═══════════════════════════════════
            result = await auth_manager.create_subscription(
                chat_id=chat_id,
                payment_id=payment_id,
            )

            if not result.get("success"):
                logger.error(
                    "auth_manager.create_subscription failed "
                    "for {}: {}".format(
                        chat_id, result.get("message")
                    )
                )

                if send_message:
                    await send_message(
                        chat_id,
                        "⚠️ Payment received but activation "
                        "failed.\n\n"
                        "Payment ID: {}\n\n"
                        "Please contact support.".format(
                            payment_id
                        )
                    )
                return

            # ── Extract info from auth result ──
            token = result.get("token", "N/A")
            expiry = result.get("expiry_date", "N/A")

            # Format expiry for display
            expiry_display = expiry
            if expiry and expiry != "N/A":
                try:
                    exp_dt = datetime.strptime(
                        expiry, "%Y-%m-%d %H:%M:%S"
                    )
                    expiry_display = exp_dt.strftime(
                        "%d/%m/%Y %I:%M %p"
                    )
                except (ValueError, TypeError):
                    expiry_display = expiry[:10]

            # ── Update payment record ──
            self._update_payment_status(
                order_id=order_id,
                status="completed",
                payment_id=payment_id,
                token=token,
            )

            # ── Send success message to user ──
            if send_message:
                success_msg = (
                    "✅ Payment Successful!\n\n"
                    "🎉 Your premium access is now ACTIVE!\n\n"
                    "📅 Valid until: {}\n"
                    "🔑 Your token: {}\n"
                    "🔒 Locked to your account\n\n"
                    "You will now receive all trading "
                    "signals.\n".format(expiry_display, token)
                )

                if self.channel_link:
                    success_msg += (
                        "\n🔗 Join premium channel: "
                        "{}\n".format(self.channel_link)
                    )

                success_msg += (
                    "\n💡 Save your token for reference.\n"
                    "Enjoy your premium experience! 🚀"
                )

                await send_message(chat_id, success_msg)

            # ── Notify admins ──
            if send_message and self.admin_ids:
                admin_msg = (
                    "💰 NEW PAYMENT!\n\n"
                    "👤 Chat ID: {}\n"
                    "💳 Payment: {}\n"
                    "📋 Order: {}\n"
                    "💵 Amount: ₹{}\n"
                    "🔑 Token: {}\n"
                    "📅 Expires: {}\n"
                    "⏰ Time: {}".format(
                        chat_id,
                        payment_id,
                        order_id,
                        self.price_inr,
                        token,
                        expiry_display,
                        datetime.now().strftime(
                            "%d/%m/%Y %I:%M:%S %p"
                        ),
                    )
                )

                for admin_id in self.admin_ids:
                    try:
                        await send_message(admin_id, admin_msg)
                    except Exception as e:
                        logger.error(
                            "Admin notify failed {}: {}".format(
                                admin_id, e
                            )
                        )

            logger.info(
                "✅ Payment processed: chat={}, token={}, "
                "expires={}".format(
                    chat_id, token, expiry_display
                )
            )

        except Exception as e:
            logger.error(
                "CRITICAL payment processing error for "
                "{}: {}".format(chat_id, e),
                exc_info=True,
            )

            # Emergency admin notification
            if send_message and self.admin_ids:
                for admin_id in self.admin_ids:
                    try:
                        await send_message(
                            admin_id,
                            "🚨 PAYMENT FAILED!\n\n"
                            "Chat: {}\n"
                            "Payment: {}\n"
                            "Error: {}\n\n"
                            "MANUAL ACTIVATION NEEDED!".format(
                                chat_id, payment_id, str(e)
                            )
                        )
                    except Exception:
                        pass

    # ═════════════════════════════════════
    #  SIGNATURE VERIFICATION
    # ═════════════════════════════════════

    def verify_payment_signature(
        self, payment_id, order_id, signature
    ):
        """
        Verify Razorpay payment signature.

        Used for webhook verification.
        Does NOT activate anything — just checks
        if signature is valid.

        Args:
            payment_id (str):  razorpay_payment_id
            order_id (str):    razorpay_order_id
            signature (str):   razorpay_signature

        Returns:
            bool: True if signature is valid
        """
        if not self.client:
            return False

        try:
            params = {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
            self.client.utility.verify_payment_signature(params)
            logger.info(
                "✅ Signature verified: {}".format(payment_id)
            )
            return True

        except Exception as e:
            logger.warning(
                "❌ Signature failed: {} - {}".format(
                    payment_id, e
                )
            )
            return False

    # ═════════════════════════════════════
    #  WEBHOOK HANDLER (future server mode)
    # ═════════════════════════════════════

    async def handle_webhook(
        self, webhook_body, webhook_signature,
        webhook_secret, send_message=None
    ):
        """
        Handle incoming Razorpay webhook.

        When payment is confirmed via webhook:
        → Calls auth_manager.create_subscription()
        → auth.py does all security work

        Args:
            webhook_body (dict):       POST body
            webhook_signature (str):   X-Razorpay-Signature
            webhook_secret (str):      Your webhook secret
            send_message:              async func(chat_id, text)

        Returns:
            bool: True if processed
        """
        try:
            # Verify signature
            import hmac
            import hashlib
            import json

            body_str = json.dumps(
                webhook_body, separators=(",", ":")
            )
            expected = hmac.new(
                webhook_secret.encode("utf-8"),
                body_str.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(
                expected, webhook_signature
            ):
                logger.warning("Webhook signature FAILED")
                return False

            # Process event
            event = webhook_body.get("event", "")

            if event == "payment_link.paid":
                payload = webhook_body.get("payload", {})
                link_entity = payload.get(
                    "payment_link", {}
                ).get("entity", {})
                pay_entity = payload.get(
                    "payment", {}
                ).get("entity", {})

                link_id = link_entity.get("id", "")
                payment_id = pay_entity.get("id", "")
                notes = link_entity.get("notes", {})
                chat_id = int(notes.get("chat_id", 0))

                if chat_id:
                    # auth.py handles everything
                    await self._handle_successful_payment(
                        chat_id=chat_id,
                        payment_id=payment_id,
                        order_id=link_id,
                        send_message=send_message,
                    )
                    return True

            return True

        except Exception as e:
            logger.error(
                "Webhook error: {}".format(e),
                exc_info=True,
            )
            return False

    # ═════════════════════════════════════
    #  PAYMENT RECORD STORAGE
    #  (simple in-memory, DB in Phase 12)
    # ═════════════════════════════════════

    def _save_payment_record(
        self, chat_id, order_id, payment_url,
        receipt, status
    ):
        """Save payment record to memory (and DB if available)."""
        record = {
            "chat_id": chat_id,
            "order_id": order_id,
            "payment_url": payment_url,
            "receipt": receipt,
            "amount_paise": self.price_paise,
            "currency": self.currency,
            "status": status,
            "payment_id": None,
            "token": None,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }

        self._payment_records[order_id] = record

        # Save to DB if available
        if DB_AVAILABLE and db_manager:
            try:
                db_manager.save_payment(record)
            except Exception as e:
                logger.warning(
                    "DB save payment warning: {}".format(e)
                )

    def _get_payment_record(self, order_id):
        """Get payment record by order ID."""
        return self._payment_records.get(order_id)

    def _get_pending_payment(self, chat_id):
        """Find pending payment for a chat_id."""
        for oid, record in self._payment_records.items():
            if (record.get("chat_id") == chat_id and
                    record.get("status") == "created"):
                return record
        return None

    def _update_payment_status(
        self, order_id, status,
        payment_id=None, token=None
    ):
        """Update payment record status."""
        record = self._payment_records.get(order_id)
        if record:
            record["status"] = status
            if payment_id:
                record["payment_id"] = payment_id
            if token:
                record["token"] = token
            if status == "completed":
                record["completed_at"] = (
                    datetime.now().isoformat()
                )

    # ═════════════════════════════════════
    #  INFO / STATUS
    # ═════════════════════════════════════

    def get_mode_info(self):
        """Return current payment mode information."""
        if self.use_razorpay:
            return (
                "💳 Mode: RAZORPAY (Real)\n"
                "💰 Price: ₹{}\n"
                "📅 Duration: {} days\n"
                "🔐 Tokens: managed by auth.py".format(
                    self.price_inr, self.sub_days
                )
            )
        else:
            return (
                "💳 Mode: FAKE (Testing)\n"
                "💰 Price: ₹{}\n"
                "📅 Duration: {} days\n"
                "🔐 Tokens: managed by auth.py\n"
                "🔧 Use /gentoken to create tokens".format(
                    self.price_inr, self.sub_days
                )
            )

    def get_payment_stats(self):
        """Get payment statistics."""
        total = len(self._payment_records)
        completed = sum(
            1 for r in self._payment_records.values()
            if r.get("status") == "completed"
        )
        pending = sum(
            1 for r in self._payment_records.values()
            if r.get("status") == "created"
        )
        failed = total - completed - pending

        return {
            "total_payments": total,
            "completed": completed,
            "pending": pending,
            "failed": failed,
            "total_revenue": completed * self.price_inr,
        }


# ═════════════════════════════════════════
# MODULE-LEVEL SINGLETON
# ═════════════════════════════════════════

# Replace the bottom of razorpay_pay.py:

try:
    payment_manager = PaymentManager()
    print("[PAYMENT] ✅ Payment module loaded")
except PaymentError as e:
    print("[PAYMENT] ❌ Payment init failed: {}".format(e))
    print("[PAYMENT] ⚠️ Falling back to fake mode")

    # Create a safe fallback instance
    import os
    os.environ["USE_RAZORPAY"] = "false"

    # Temporarily patch Config
    try:
        Config.USE_RAZORPAY = False
    except Exception:
        pass

    payment_manager = PaymentManager()
    print("[PAYMENT] ✅ Payment module loaded (fake mode fallback)")
except Exception as e:
    print("[PAYMENT] ❌ Unexpected error: {}".format(e))
    payment_manager = None

print("[PAYMENT] ✅ Payment module loaded")