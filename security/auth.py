# ============================================
# CRYPTO SIGNAL BOT - SECURITY & AUTH
# ============================================
# Production-grade authentication system.
#
# Responsibilities:
#   - Token generation (CSB-UUID4 format)
#   - Token validation (5-point check)
#   - Subscription creation & activation
#   - Chat ID locking (permanent, one-way)
#   - Expiry management & auto-cleanup
#   - Anti-sharing detection & flagging
#   - Full audit trail logging
#
# Token format: CSB-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
#   - Prefix "CSB-" for identification
#   - UUID4 body for uniqueness
#   - ~40 characters total
#   - Case-insensitive validation
#
# Security rules (HARD enforced):
#   1. Token locked to ONE chat_id permanently
#   2. Cannot unlock/transfer a token ever
#   3. Cannot reuse expired tokens
#   4. 3 sharing attempts → user flagged
#   5. All attempts logged (success + failure)
#   6. No grace period after expiry
#
# Usage:
#   from security.auth import auth_manager
#   result = await auth_manager.validate_token(token, chat_id)
# ============================================

import uuid
import logging
from datetime import datetime, timedelta

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
    print("[AUTH] ⚠️ Database not available — "
          "using in-memory security store")

# ============================================
# LOGGING
# ============================================

logger = logging.getLogger("auth")

# ============================================
# CONSTANTS
# ============================================

TOKEN_PREFIX = "CSB-"
MAX_SHARING_ATTEMPTS = 3
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class AuthManager:
    """
    Authentication and subscription security manager.

    Manages the complete token lifecycle:
    generate → validate → activate → monitor → expire

    All tokens are permanently locked to a single
    Telegram chat_id upon activation. This binding
    is one-way and irreversible.

    Anti-sharing system tracks attempts to use tokens
    belonging to other users and flags repeat offenders.

    Audit log records every authentication event
    for security review.

    Attributes:
        _tokens (dict):            Token store {token: data}
        _subscriptions (dict):     Subscription store {chat_id: data}
        _sharing_attempts (dict):  Sharing tracker {chat_id: count}
        _flagged_users (set):      Users flagged for sharing
        _audit_log (list):         Security event log
        _token_usage (dict):       Token → chat_id lock map
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        """
        Initialize the Authentication Manager.

        Sets up:
        - In-memory token store (primary or fallback)
        - Subscription tracking
        - Anti-sharing counters
        - Audit log buffer (last 500 events)
        - Flagged user set

        Loads subscription duration from Config.
        """
        # ------ Token store ------
        # {token_str: {token, chat_id, created_at, expires_at,
        #              is_active, is_used, payment_id, activated_at}}
        self._tokens = {}

        # ------ Subscription store ------
        # {chat_id: {chat_id, token, start_date, end_date,
        #            is_active, payment_id}}
        self._subscriptions = {}

        # ------ Token → chat_id lock ------
        # Once set, NEVER changes
        self._token_usage = {}

        # ------ Anti-sharing ------
        self._sharing_attempts = {}  # {chat_id: count}
        self._flagged_users = set()

        # ------ Audit log ------
        self._audit_log = []
        self._max_audit_entries = 500

        # ------ Config ------
        try:
            self._sub_days = int(Config.SUBSCRIPTION_DAYS)
        except (AttributeError, ValueError, TypeError):
            self._sub_days = 28

        try:
            self._sub_price = Config.SUBSCRIPTION_PRICE
        except AttributeError:
            self._sub_price = 999

        print("[AUTH] ✅ AuthManager initialized")
        print("[AUTH]    Token prefix: {}".format(TOKEN_PREFIX))
        print("[AUTH]    Subscription: {} days".format(self._sub_days))
        print("[AUTH]    Max sharing attempts: {}".format(
            MAX_SHARING_ATTEMPTS
        ))
        print("[AUTH]    Database: {}".format(
            "connected" if DB_AVAILABLE else "in-memory"
        ))

    # ============================================
    # FUNCTION 2: AUDIT LOGGING
    # ============================================

    def _log_event(self, event_type, chat_id=None,
                   token=None, details="", success=True):
        """
        Record a security event in the audit log.

        Every authentication action is logged:
        - TOKEN_GENERATED
        - TOKEN_VALIDATED
        - TOKEN_ACTIVATED
        - TOKEN_REJECTED
        - SHARING_ATTEMPT
        - SUBSCRIPTION_CREATED
        - SUBSCRIPTION_EXPIRED
        - SUBSCRIPTION_REVOKED
        - AUTH_CHECK
        - SUSPICIOUS_ACTIVITY

        Args:
            event_type (str):  Event category
            chat_id (int):     User involved (if any)
            token (str):       Token involved (masked in log)
            details (str):     Human-readable description
            success (bool):    Whether the action succeeded
        """
        try:
            # Mask token for log safety
            masked_token = ""
            if token:
                if len(token) >= 12:
                    masked_token = token[:8] + "****" + token[-4:]
                else:
                    masked_token = "****"

            entry = {
                "timestamp": datetime.now().strftime(DATE_FORMAT),
                "event": event_type,
                "chat_id": chat_id,
                "token": masked_token,
                "details": details,
                "success": success,
            }

            self._audit_log.append(entry)

            # Keep bounded
            if len(self._audit_log) > self._max_audit_entries:
                self._audit_log = self._audit_log[
                    -self._max_audit_entries:
                ]

            # Also log to file logger
            level = logging.INFO if success else logging.WARNING
            logger.log(
                level,
                "[{}] {} | chat:{} | token:{} | {}".format(
                    "✅" if success else "❌",
                    event_type,
                    chat_id or "N/A",
                    masked_token or "N/A",
                    details,
                )
            )

            # Console output for important events
            if event_type in (
                "SHARING_ATTEMPT", "SUSPICIOUS_ACTIVITY",
                "TOKEN_ACTIVATED", "SUBSCRIPTION_EXPIRED",
                "SUBSCRIPTION_REVOKED"
            ):
                icon = "✅" if success else "🚨"
                print("[AUTH] {} {} | chat:{} | {}".format(
                    icon, event_type, chat_id, details
                ))

        except Exception as e:
            print("[AUTH] ❌ Audit log error: {}".format(e))

    # ============================================
    # FUNCTION 3: GENERATE TOKEN
    # ============================================

    async def generate_token(self):

        """
        Generate a unique activation token.

        Format: CSB-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        - "CSB-" prefix for easy identification
        - UUID4 body guarantees uniqueness
        - Uppercase for consistency
        - ~40 characters total

        Verifies uniqueness against existing tokens
        (collision probability is astronomically low
        with UUID4, but we check anyway).

        Returns:
            str: Unique token string, or None on error
        """
        try:
            max_attempts = 5

            for attempt in range(max_attempts):
                # Generate token
                token_body = str(uuid.uuid4()).upper()
                token_str = "{}{}".format(TOKEN_PREFIX, token_body)

                # Check uniqueness — memory
                if token_str in self._tokens:
                    continue

                # Check uniqueness — database
                if DB_AVAILABLE and db_manager:
                    try:
                        existing = await db_manager.get_token(token_str)
                        if existing:
                            continue
                    except Exception:
                        pass

                # Token is unique
                self._log_event(
                    "TOKEN_GENERATED",
                    token=token_str,
                    details="New token generated",
                    success=True,
                )

                print("[AUTH] 🔑 Token generated: {}****".format(
                    token_str[:12]
                ))

                return token_str

            # Exhausted attempts (should never happen)
            print("[AUTH] ❌ Failed to generate unique token "
                  "after {} attempts".format(max_attempts))
            return None

        except Exception as e:
            print("[AUTH] ❌ Token generation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 4: CREATE SUBSCRIPTION
    # ============================================

    async def create_subscription(self, chat_id,
                                   payment_id="FAKE"):
        """
        Create a new subscription for a user.

        Pipeline:
        1. Generate unique token
        2. Calculate expiry (today + subscription days)
        3. Store token in token store (locked to chat_id)
        4. Store subscription record
        5. Save to database
        6. Log the event

        The token is immediately locked to the chat_id
        upon creation. No separate activation needed
        when created via this method.

        Args:
            chat_id (int):      Telegram chat ID
            payment_id (str):   Payment reference
                               "FAKE" for test mode

        Returns:
            dict: {
                "success": bool,
                "token": str or None,
                "expiry_date": str or None,
                "chat_id": int,
                "message": str
            }
        """
        try:
            if not chat_id:
                return {
                    "success": False,
                    "token": None,
                    "expiry_date": None,
                    "chat_id": chat_id,
                    "message": "Invalid chat ID",
                }

            # ------ Generate token ------
            token_str = await self.generate_token()
            if not token_str:
                return {
                    "success": False,
                    "token": None,
                    "expiry_date": None,
                    "chat_id": chat_id,
                    "message": "Token generation failed",
                }

            # ------ Calculate dates ------
            now = datetime.now()
            expiry = now + timedelta(days=self._sub_days)
            now_str = now.strftime(DATE_FORMAT)
            expiry_str = expiry.strftime(DATE_FORMAT)

            # ------ Store token (locked to chat_id) ------
            token_data = {
                "token": token_str,
                "chat_id": chat_id,
                "created_at": now_str,
                "activated_at": now_str,
                "expires_at": expiry_str,
                "is_active": True,
                "is_used": True,
                "payment_id": payment_id,
            }

            self._tokens[token_str] = token_data
            self._token_usage[token_str] = chat_id

            # ------ Store subscription ------
            sub_data = {
                "chat_id": chat_id,
                "token": token_str,
                "start_date": now_str,
                "end_date": expiry_str,
                "is_active": True,
                "payment_id": payment_id,
            }

            self._subscriptions[chat_id] = sub_data

            # ------ Save to database ------
            if DB_AVAILABLE and db_manager:
                try:
                    await db_manager.create_token(
                        token_str,
                        days=self._sub_days,
                    )
                except TypeError:
                    try:
                        await db_manager.create_token(token_str)
                    except Exception:
                        pass

                try:
                    await db_manager.activate_token(token_str, chat_id)
                except Exception:
                    pass

            # ------ Log ------
            self._log_event(
                "SUBSCRIPTION_CREATED",
                chat_id=chat_id,
                token=token_str,
                details="Payment: {} | Expires: {}".format(
                    payment_id, expiry_str[:10]
                ),
                success=True,
            )

            print("[AUTH] ✅ Subscription created for "
                  "chat:{} | Expires: {}".format(
                      chat_id, expiry_str[:10]
                  ))

            return {
                "success": True,
                "token": token_str,
                "expiry_date": expiry_str,
                "chat_id": chat_id,
                "message": "Subscription created successfully",
            }

        except Exception as e:
            print("[AUTH] ❌ Create subscription error: {}".format(e))

            self._log_event(
                "SUBSCRIPTION_CREATED",
                chat_id=chat_id,
                details="FAILED: {}".format(e),
                success=False,
            )

            return {
                "success": False,
                "token": None,
                "expiry_date": None,
                "chat_id": chat_id,
                "message": "Subscription creation failed: "
                           "{}".format(str(e)),
            }

    # ============================================
    # FUNCTION 5: VALIDATE TOKEN (5-point check)
    # ============================================

    async def validate_token(self, token, chat_id):
        """
        Validate a token with 5 security checks.

        Check order (fail-fast):
        ┌────────────────────────────────────────┐
        │ 1. FORMAT:  Starts with "CSB-"?        │
        │ 2. EXISTS:  Token in database/store?    │
        │ 3. LOCKED:  Token locked to OTHER user? │
        │ 4. EXPIRED: Past expiry date?           │
        │ 5. ACTIVE:  Already active for user?    │
        └────────────────────────────────────────┘

        Check 3 (LOCKED) triggers anti-sharing logic
        if the token belongs to a different chat_id.

        Args:
            token (str):    Token string to validate
            chat_id (int):  Chat ID attempting validation

        Returns:
            dict: {
                "status": "VALID" | "INVALID_TOKEN" |
                          "LOCKED" | "EXPIRED" |
                          "ALREADY_ACTIVE" | "ERROR",
                "message": str (human-readable),
                "expiry_date": str or None
            }
        """
        try:
            if not token or not chat_id:
                self._log_event(
                    "TOKEN_REJECTED",
                    chat_id=chat_id,
                    token=token,
                    details="Empty token or chat_id",
                    success=False,
                )
                return {
                    "status": "INVALID_TOKEN",
                    "message": "Token or user ID is missing.",
                    "expiry_date": None,
                }

            # Normalize token
            token = token.strip().upper()

            # ============================
            # CHECK 1: FORMAT VALIDATION
            # ============================
            if not token.startswith(TOKEN_PREFIX):
                self._log_event(
                    "TOKEN_REJECTED",
                    chat_id=chat_id,
                    token=token,
                    details="Invalid format — missing "
                            "CSB- prefix",
                    success=False,
                )
                return {
                    "status": "INVALID_TOKEN",
                    "message": "Invalid token format. "
                               "Tokens start with 'CSB-'.",
                    "expiry_date": None,
                }

            if len(token) < 30:
                self._log_event(
                    "TOKEN_REJECTED",
                    chat_id=chat_id,
                    token=token,
                    details="Token too short: {} chars".format(
                        len(token)
                    ),
                    success=False,
                )
                return {
                    "status": "INVALID_TOKEN",
                    "message": "Invalid token format. "
                               "Please check and try again.",
                    "expiry_date": None,
                }

            # ============================
            # CHECK 2: TOKEN EXISTS
            # ============================
            token_data = await self._get_token_data(token)

            if not token_data:
                self._log_event(
                    "TOKEN_REJECTED",
                    chat_id=chat_id,
                    token=token,
                    details="Token not found in any store",
                    success=False,
                )
                return {
                    "status": "INVALID_TOKEN",
                    "message": "Token not found. Please "
                               "check your token and try again.",
                    "expiry_date": None,
                }

            # ============================
            # CHECK 3: LOCKED TO OTHER USER
            # ============================
            locked_to = token_data.get(
                "chat_id",
                token_data.get("activated_by")
            )

            is_used = token_data.get("is_used", False)

            if locked_to and is_used and int(locked_to) != int(chat_id):
                # SHARING ATTEMPT DETECTED
                self._record_sharing_attempt(chat_id, token)

                self._log_event(
                    "SHARING_ATTEMPT",
                    chat_id=chat_id,
                    token=token,
                    details="Token locked to chat:{} — "
                            "attempt by chat:{}".format(
                                locked_to, chat_id
                            ),
                    success=False,
                )

                attempts = self._sharing_attempts.get(chat_id, 0)

                return {
                    "status": "LOCKED",
                    "message": "This token is already activated "
                               "on another account. Each token "
                               "can only be used on ONE account. "
                               "({}/{} attempts)".format(
                                   attempts, MAX_SHARING_ATTEMPTS
                               ),
                    "expiry_date": None,
                }

            # ============================
            # CHECK 4: EXPIRED
            # ============================
            expires_str = token_data.get("expires_at", "")
            if expires_str:
                try:
                    if isinstance(expires_str, str):
                        expires_dt = datetime.strptime(
                            expires_str, DATE_FORMAT
                        )
                    else:
                        expires_dt = expires_str

                    if datetime.now() > expires_dt:
                        self._log_event(
                            "TOKEN_REJECTED",
                            chat_id=chat_id,
                            token=token,
                            details="Expired on {}".format(
                                expires_str[:10]
                            ),
                            success=False,
                        )
                        return {
                            "status": "EXPIRED",
                            "message": "This token has expired "
                                       "on {}. Please purchase "
                                       "a new subscription.".format(
                                           expires_str[:10]
                                       ),
                            "expiry_date": expires_str,
                        }
                except (ValueError, TypeError):
                    pass

            # ============================
            # CHECK 5: ALREADY ACTIVE
            # ============================
            if (is_used and locked_to and
                    int(locked_to) == int(chat_id)):

                is_active = token_data.get("is_active", False)

                if is_active:
                    self._log_event(
                        "TOKEN_VALIDATED",
                        chat_id=chat_id,
                        token=token,
                        details="Already active for this user",
                        success=True,
                    )
                    return {
                        "status": "ALREADY_ACTIVE",
                        "message": "This token is already "
                                   "active on your account!",
                        "expiry_date": expires_str,
                    }

            # ============================
            # ALL CHECKS PASSED → VALID
            # ============================
            self._log_event(
                "TOKEN_VALIDATED",
                chat_id=chat_id,
                token=token,
                details="All 5 checks passed",
                success=True,
            )

            return {
                "status": "VALID",
                "message": "Token is valid and ready "
                           "to activate.",
                "expiry_date": expires_str if expires_str
                    else None,
            }

        except Exception as e:
            print("[AUTH] ❌ Token validation error: {}".format(e))

            self._log_event(
                "TOKEN_REJECTED",
                chat_id=chat_id,
                token=token,
                details="ERROR: {}".format(e),
                success=False,
            )

            return {
                "status": "ERROR",
                "message": "Validation error. Please "
                           "try again later.",
                "expiry_date": None,
            }

    # ============================================
    # FUNCTION 6: ACTIVATE TOKEN
    # ============================================

    async def activate_token(self, token, chat_id):
        """
        Activate a token and bind it permanently
        to a chat_id.

        Pipeline:
        1. Validate token (5-point check)
        2. If VALID or ALREADY_ACTIVE → proceed
        3. Lock token to chat_id (permanent)
        4. Create/update subscription
        5. Save to database
        6. Log activation event

        The lock is PERMANENT. Once a token is bound
        to a chat_id, it can never be transferred.

        Args:
            token (str):    Token string
            chat_id (int):  Telegram chat ID

        Returns:
            dict: {
                "success": bool,
                "status": str,
                "message": str,
                "expiry_date": str or None
            }
        """
        try:
            if not token or not chat_id:
                return {
                    "success": False,
                    "status": "ERROR",
                    "message": "Token or user ID missing.",
                    "expiry_date": None,
                }

            token = token.strip().upper()

            # ------ Validate first ------
            validation = await self.validate_token(token, chat_id)
            status = validation["status"]

            # Already active → treat as success
            if status == "ALREADY_ACTIVE":
                return {
                    "success": True,
                    "status": "ALREADY_ACTIVE",
                    "message": validation["message"],
                    "expiry_date": validation["expiry_date"],
                }

            # Not valid → return the validation error
            if status != "VALID":
                return {
                    "success": False,
                    "status": status,
                    "message": validation["message"],
                    "expiry_date": None,
                }

            # ------ Lock token to chat_id ------
            now = datetime.now()
            now_str = now.strftime(DATE_FORMAT)

            # Get or set expiry
            token_data = self._get_token_data(token)

            if token_data and token_data.get("expires_at"):
                expiry_str = token_data["expires_at"]
            else:
                expiry = now + timedelta(days=self._sub_days)
                expiry_str = expiry.strftime(DATE_FORMAT)

            # Update token store
            if token in self._tokens:
                self._tokens[token]["chat_id"] = chat_id
                self._tokens[token]["is_used"] = True
                self._tokens[token]["is_active"] = True
                self._tokens[token]["activated_at"] = now_str
            else:
                self._tokens[token] = {
                    "token": token,
                    "chat_id": chat_id,
                    "created_at": now_str,
                    "activated_at": now_str,
                    "expires_at": expiry_str,
                    "is_active": True,
                    "is_used": True,
                    "payment_id": "ACTIVATED",
                }

            # Permanent lock
            self._token_usage[token] = chat_id

            # Create subscription
            self._subscriptions[chat_id] = {
                "chat_id": chat_id,
                "token": token,
                "start_date": now_str,
                "end_date": expiry_str,
                "is_active": True,
                "payment_id": self._tokens[token].get(
                    "payment_id", "ACTIVATED"
                ),
            }

            # ------ Save to database ------
            if DB_AVAILABLE and db_manager:
                try:
                    await db_manager.activate_token(token, chat_id)
                except Exception as e:
                    print("[AUTH] DB activate warning: {}".format(e))

            # ------ Log ------
            self._log_event(
                "TOKEN_ACTIVATED",
                chat_id=chat_id,
                token=token,
                details="Locked to chat:{} | "
                        "Expires: {}".format(
                            chat_id, expiry_str[:10]
                        ),
                success=True,
            )

            print("[AUTH] ✅ Token activated | "
                  "chat:{} | expires:{}".format(
                      chat_id, expiry_str[:10]
                  ))

            return {
                "success": True,
                "status": "ACTIVATED",
                "message": "Token activated successfully! "
                           "Your subscription is now active.",
                "expiry_date": expiry_str,
            }

        except Exception as e:
            print("[AUTH] ❌ Activation error: {}".format(e))

            self._log_event(
                "TOKEN_ACTIVATED",
                chat_id=chat_id,
                token=token,
                details="FAILED: {}".format(e),
                success=False,
            )

            return {
                "success": False,
                "status": "ERROR",
                "message": "Activation failed. Please "
                           "try again.",
                "expiry_date": None,
            }

    # ============================================
    # FUNCTION 7: IS AUTHORIZED
    # ============================================

    async def is_authorized(self, chat_id):
        """
        Quick authorization check.

        Fast path (<1ms): checks in-memory subscription
        store first. Falls back to database if needed.

        Checks:
        1. Subscription exists for chat_id
        2. Subscription is marked active
        3. Current date is before expiry date

        If expired → auto-deactivate and return False.

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            bool: True if authorized, False otherwise
        """
        try:
            if not chat_id:
                return False

            chat_id = int(chat_id)

            # ------ Fast path: memory check ------
            sub = self._subscriptions.get(chat_id)

            if sub and sub.get("is_active"):
                end_str = sub.get("end_date", "")
                if end_str:
                    try:
                        end_dt = datetime.strptime(
                            end_str, DATE_FORMAT
                        )
                        if datetime.now() <= end_dt:
                            return True
                        else:
                            # Auto-expire
                            sub["is_active"] = False
                            self._log_event(
                                "AUTH_CHECK",
                                chat_id=chat_id,
                                details="Auto-expired during "
                                        "auth check",
                                success=False,
                            )
                            return False
                    except (ValueError, TypeError):
                        return True
                return True

            # ------ Slow path: database check ------
            if DB_AVAILABLE and db_manager:
                try:
                    result = await db_manager.is_subscribed(chat_id)
                    if result:
                        return True
                except Exception:
                    pass

            return False

        except Exception as e:
            print("[AUTH] ❌ Auth check error: {}".format(e))
            return False

    # ============================================
    # FUNCTION 8: CHECK AND EXPIRE
    # ============================================

    async def check_and_expire(self):
        """
        Find and deactivate all expired subscriptions.

        Called periodically by the scheduler (every hour).

        Pipeline:
        1. Scan all subscriptions
        2. Check each expiry date against now
        3. Deactivate expired ones
        4. Log each expiry
        5. Return list of expired chat_ids
           (for sending notifications)

        Args: None

        Returns:
            list[int]: Chat IDs of newly expired users
        """
        expired_users = []

        try:
            now = datetime.now()

            # ------ Check memory subscriptions ------
            for chat_id, sub in list(self._subscriptions.items()):
                if not sub.get("is_active"):
                    continue

                end_str = sub.get("end_date", "")
                if not end_str:
                    continue

                try:
                    if isinstance(end_str, str):
                        end_dt = datetime.strptime(
                            end_str, DATE_FORMAT
                        )
                    else:
                        end_dt = end_str

                    if now > end_dt:
                        # Deactivate
                        sub["is_active"] = False

                        # Deactivate token too
                        token_str = sub.get("token", "")
                        if token_str and token_str in self._tokens:
                            self._tokens[token_str]["is_active"] = False

                        expired_users.append(chat_id)

                        self._log_event(
                            "SUBSCRIPTION_EXPIRED",
                            chat_id=chat_id,
                            token=token_str,
                            details="Expired on {}".format(
                                end_str[:10]
                            ),
                            success=True,
                        )

                except (ValueError, TypeError):
                    continue

            if expired_users:
                print("[AUTH] ⏰ {} subscription(s) expired: "
                      "{}".format(
                          len(expired_users), expired_users
                      ))
            else:
                print("[AUTH] ✅ No expired subscriptions")

            return expired_users

        except Exception as e:
            print("[AUTH] ❌ Expiry check error: {}".format(e))
            return expired_users

    # ============================================
    # FUNCTION 9: GET SUBSCRIPTION INFO
    # ============================================

    async def get_subscription_info(self, chat_id):
        """
        Get full subscription details for a user.

        Returns comprehensive info including:
        - Active status
        - Masked token (first 8 + last 4 visible)
        - Start and end dates
        - Days remaining
        - Payment reference
        - Whether user is flagged for sharing

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            dict: {
                "has_subscription": bool,
                "is_active": bool,
                "token_masked": str,
                "start_date": str,
                "end_date": str,
                "days_remaining": int,
                "payment_id": str,
                "is_flagged": bool,
                "sharing_attempts": int
            }
        """
        default = {
            "has_subscription": False,
            "is_active": False,
            "token_masked": "****",
            "start_date": "N/A",
            "end_date": "N/A",
            "days_remaining": 0,
            "payment_id": "N/A",
            "is_flagged": chat_id in self._flagged_users,
            "sharing_attempts": self._sharing_attempts.get(
                chat_id, 0
            ),
        }

        try:
            if not chat_id:
                return default

            chat_id = int(chat_id)

            # Check memory
            sub = self._subscriptions.get(chat_id)

            # Check database fallback
            if not sub and DB_AVAILABLE and db_manager:
                try:
                    sub = await db_manager.get_subscription(chat_id)
                except Exception:
                    pass

            if not sub:
                return default

            # Extract fields
            token_str = sub.get("token", "")
            start = sub.get("start_date", "N/A")
            end = sub.get("end_date", "N/A")
            is_active = sub.get("is_active", False)
            payment = sub.get("payment_id", "N/A")

            # Mask token
            if len(token_str) >= 12:
                masked = token_str[:8] + "****" + token_str[-4:]
            elif token_str:
                masked = "****"
            else:
                masked = "N/A"

            # Days remaining
            days_remaining = 0
            if end and end != "N/A":
                try:
                    if isinstance(end, str):
                        end_dt = datetime.strptime(end, DATE_FORMAT)
                    else:
                        end_dt = end
                    delta = end_dt - datetime.now()
                    days_remaining = max(0, delta.days)

                    # Auto-expire check
                    if days_remaining == 0 and is_active:
                        is_active = False
                        if chat_id in self._subscriptions:
                            self._subscriptions[chat_id][
                                "is_active"
                            ] = False

                except (ValueError, TypeError):
                    pass

            return {
                "has_subscription": True,
                "is_active": is_active,
                "token_masked": masked,
                "start_date": start[:10] if isinstance(start, str)
                    and len(start) >= 10 else str(start),
                "end_date": end[:10] if isinstance(end, str)
                    and len(end) >= 10 else str(end),
                "days_remaining": days_remaining,
                "payment_id": payment,
                "is_flagged": chat_id in self._flagged_users,
                "sharing_attempts": self._sharing_attempts.get(
                    chat_id, 0
                ),
            }

        except Exception as e:
            print("[AUTH] ❌ Get sub info error: {}".format(e))
            return default

    # ============================================
    # FUNCTION 10: REVOKE TOKEN (Admin)
    # ============================================

    async def revoke_token(self, token):
        """
        Administratively revoke a token immediately.

        Deactivates the token and its associated
        subscription. This is a HARD kill — no grace
        period, no undo.

        Used for:
        - Refund processing
        - Abuse detection
        - Admin override

        Args:
            token (str): Token string to revoke

        Returns:
            dict: {
                "success": bool,
                "message": str,
                "affected_chat_id": int or None
            }
        """
        try:
            if not token:
                return {
                    "success": False,
                    "message": "No token provided",
                    "affected_chat_id": None,
                }

            token = token.strip().upper()
            affected_chat = None

            # ------ Revoke in memory ------
            if token in self._tokens:
                token_data = self._tokens[token]
                affected_chat = token_data.get("chat_id")

                token_data["is_active"] = False
                token_data["is_used"] = True

                # Deactivate linked subscription
                if affected_chat and affected_chat in self._subscriptions:
                    self._subscriptions[affected_chat]["is_active"] = False

            # ------ Revoke in database ------
            if DB_AVAILABLE and db_manager:
                try:
                    db_data = await db_manager.get_token(token)
                    if db_data:
                        affected_chat = affected_chat or db_data.get(
                            "chat_id"
                        )
                        await db_manager.deactivate_token(token)
                except Exception as e:
                    print("[AUTH] DB revoke warning: {}".format(e))

            # ------ Log ------
            self._log_event(
                "SUBSCRIPTION_REVOKED",
                chat_id=affected_chat,
                token=token,
                details="Admin revocation",
                success=True,
            )

            print("[AUTH] 🚫 Token revoked | "
                  "chat:{}".format(affected_chat))

            return {
                "success": True,
                "message": "Token revoked successfully",
                "affected_chat_id": affected_chat,
            }

        except Exception as e:
            print("[AUTH] ❌ Revoke error: {}".format(e))
            return {
                "success": False,
                "message": "Revocation failed: {}".format(e),
                "affected_chat_id": None,
            }

    # ============================================
    # ANTI-SHARING SYSTEM
    # ============================================

    def _record_sharing_attempt(self, chat_id, token):
        """
        Record a token sharing attempt.

        Increments the attempt counter for the chat_id.
        If counter reaches MAX_SHARING_ATTEMPTS (3),
        the user is flagged for suspicious activity.

        Flagged users are logged and can be reviewed
        by administrators.

        Args:
            chat_id (int): Chat ID that attempted sharing
            token (str):   Token they tried to use
        """
        try:
            chat_id = int(chat_id)

            # Increment counter
            current = self._sharing_attempts.get(chat_id, 0)
            current += 1
            self._sharing_attempts[chat_id] = current

            print("[AUTH] 🚨 SHARING ATTEMPT #{} | "
                  "chat:{}".format(current, chat_id))

            # Flag user at threshold
            if current >= MAX_SHARING_ATTEMPTS:
                if chat_id not in self._flagged_users:
                    self._flagged_users.add(chat_id)

                    self._log_event(
                        "SUSPICIOUS_ACTIVITY",
                        chat_id=chat_id,
                        token=token,
                        details="USER FLAGGED — {} sharing "
                                "attempts reached".format(current),
                        success=False,
                    )

                    print("[AUTH] 🚩 USER FLAGGED | chat:{} | "
                          "{} sharing attempts".format(
                              chat_id, current
                          ))

        except Exception as e:
            print("[AUTH] ❌ Sharing record error: {}".format(e))

    def is_user_flagged(self, chat_id):
        """
        Check if a user is flagged for sharing.

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            bool: True if flagged
        """
        return int(chat_id) in self._flagged_users

    def get_sharing_attempts(self, chat_id):
        """
        Get number of sharing attempts for a user.

        Args:
            chat_id (int): Telegram chat ID

        Returns:
            int: Number of sharing attempts
        """
        return self._sharing_attempts.get(int(chat_id), 0)

    # ============================================
    # DATA ACCESS HELPERS
    # ============================================

    async def _get_token_data(self, token):
        """
        Retrieve token data from memory or database.

        Checks memory store first (fast path), then
        falls back to database (slow path).

        Args:
            token (str): Token string (normalized)

        Returns:
            dict or None: Token data
        """
        try:
            # Memory first
            if token in self._tokens:
                return self._tokens[token]

            # Database fallback
            if DB_AVAILABLE and db_manager:
                try:
                    data = await db_manager.get_token(token)
                    if data:
                        self._tokens[token] = data
                        return data
                except Exception:
                    pass

            return None

        except Exception:
            return None

    # ============================================
    # AUDIT LOG ACCESS
    # ============================================

    def get_audit_log(self, limit=50, event_type=None,
                      chat_id=None):
        """
        Retrieve audit log entries with optional filtering.

        Args:
            limit (int):        Max entries to return
            event_type (str):   Filter by event type
            chat_id (int):      Filter by chat ID

        Returns:
            list[dict]: Matching audit entries (newest first)
        """
        try:
            entries = list(self._audit_log)

            if event_type:
                entries = [
                    e for e in entries
                    if e.get("event") == event_type
                ]

            if chat_id:
                entries = [
                    e for e in entries
                    if e.get("chat_id") == int(chat_id)
                ]

            # Newest first
            entries.reverse()

            return entries[:limit]

        except Exception:
            return []

    def get_security_stats(self):
        """
        Get security system statistics.

        Returns:
            dict: Current security metrics
        """
        try:
            active_subs = sum(
                1 for s in self._subscriptions.values()
                if s.get("is_active")
            )

            return {
                "total_tokens": len(self._tokens),
                "active_subscriptions": active_subs,
                "total_subscriptions": len(self._subscriptions),
                "flagged_users": len(self._flagged_users),
                "total_sharing_attempts": sum(
                    self._sharing_attempts.values()
                ),
                "users_with_attempts": len(
                    self._sharing_attempts
                ),
                "audit_log_entries": len(self._audit_log),
                "blocked_tokens": sum(
                    1 for t in self._tokens.values()
                    if t.get("is_used") and not t.get("is_active")
                ),
            }

        except Exception:
            return {}


# ==================================================
# MODULE-LEVEL SINGLETON
# ==================================================

auth_manager = AuthManager()

print("[AUTH] ✅ Security module loaded and ready")