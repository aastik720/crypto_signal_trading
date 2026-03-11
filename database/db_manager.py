# ============================================
# CRYPTO SIGNAL BOT - DATABASE MANAGER
# ============================================
# Handles ALL SQLite database operations using
# aiosqlite for fully async, non-blocking I/O.
#
# Tables managed:
#   1. users              - user data, subscriptions
#   2. signals_log        - trading signal history
#   3. public_channel_tracker - daily public counter
#
# Usage:
#   from database.db_manager import db
#   await db.create_tables()
#   await db.add_user("12345", "john", "John")
# ============================================

import os
import aiosqlite
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from config.settings import Config

# ==================================================
# Ensure database directory exists on import
# ==================================================

_db_directory = os.path.dirname(Config.DATABASE_PATH)

if _db_directory and not os.path.exists(_db_directory):
    try:
        os.makedirs(_db_directory, exist_ok=True)
        print("[DATABASE] Created directory: {}".format(
            _db_directory
        ))
    except OSError as e:
        print("[DATABASE ERROR] Cannot create directory "
              "'{}': {}".format(_db_directory, e))


class DatabaseManager:
    """
    Async database manager for CryptoSignal Bot.
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self):
        self.db_path = Config.DATABASE_PATH
        self._tables_created = False
        print("[DATABASE] Manager initialized | "
              "Path: {}".format(self.db_path))

    # ============================================
    # CONNECTION HELPER
    # ============================================

    @asynccontextmanager
    async def _get_db(self):
        db = await aiosqlite.connect(self.db_path)
        try:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            yield db
        finally:
            await db.close()

    # ============================================
    # TABLE SAFETY NET
    # ============================================

    async def _ensure_tables(self):
        if not self._tables_created:
            await self.create_tables()

    # ============================================
    # FUNCTION 2: CREATE TABLES
    # ============================================

    async def create_tables(self):
        try:
            async with self._get_db() as db:

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id               TEXT    UNIQUE NOT NULL,
                        username              TEXT,
                        first_name            TEXT,
                        join_date             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active             BOOLEAN   DEFAULT 0,
                        token                 TEXT    UNIQUE,
                        token_activated_date  TIMESTAMP,
                        token_expiry_date     TIMESTAMP,
                        locked_chat_id        TEXT,
                        total_signals_received INTEGER DEFAULT 0,
                        last_signal_time      TIMESTAMP,
                        payment_id            TEXT,
                        created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS signals_log (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        pair             TEXT    NOT NULL,
                        direction        TEXT    NOT NULL,
                        entry_price      REAL    NOT NULL,
                        target_1         REAL,
                        target_2         REAL,
                        stop_loss        REAL,
                        confidence       REAL    NOT NULL,
                        signal_time      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        was_sent_public  BOOLEAN   DEFAULT 0,
                        was_sent_private BOOLEAN   DEFAULT 0,
                        result           TEXT,
                        pnl_percent      REAL
                    )
                """)

                await db.execute("""
                    CREATE TABLE IF NOT EXISTS public_channel_tracker (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        date                DATE    NOT NULL UNIQUE,
                        signals_sent_count  INTEGER DEFAULT 0,
                        last_signal_time    TIMESTAMP
                    )
                """)

                await db.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_users_chat_id
                    ON users (chat_id)
                """)

                await db.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_users_token
                    ON users (token)
                """)

                await db.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_users_active
                    ON users (is_active)
                """)

                await db.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_signals_time
                    ON signals_log (signal_time)
                """)

                await db.commit()
                self._tables_created = True

                print("[DATABASE] ✅ All tables created/"
                      "verified successfully")
                return True

        except Exception as e:
            print("[DATABASE ERROR] Failed to create "
                  "tables: {}".format(e))
            return False

    # ============================================
    # FUNCTION 3: ADD USER
    # ============================================

    async def add_user(self, chat_id, username=None,
                       first_name=None):
        await self._ensure_tables()
        try:
            async with self._get_db() as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO users
                        (chat_id, username, first_name)
                    VALUES (?, ?, ?)
                    """,
                    (str(chat_id), username, first_name)
                )
                await db.commit()

                print("[DATABASE] User registered: "
                      "chat_id={} name={}".format(
                          chat_id,
                          first_name or username
                          or "Unknown",
                      ))
                return True

        except Exception as e:
            print("[DATABASE ERROR] add_user failed "
                  "for chat_id={}: {}".format(
                      chat_id, e
                  ))
            return False

    # ============================================
    # FUNCTION 4: GET USER
    # ============================================

    async def get_user(self, chat_id):
        await self._ensure_tables()
        try:
            async with self._get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM users "
                    "WHERE chat_id = ?",
                    (str(chat_id),)
                )
                row = await cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print("[DATABASE ERROR] get_user failed "
                  "for chat_id={}: {}".format(
                      chat_id, e
                  ))
            return None

    # ============================================
    # FUNCTION 5: GET ALL ACTIVE USERS
    # ============================================

    async def get_all_active_users(self):
        await self._ensure_tables()
        try:
            async with self._get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM users "
                    "WHERE is_active = 1"
                )
                rows = await cursor.fetchall()
                users = [dict(row) for row in rows]

                print("[DATABASE] Active users found: "
                      "{}".format(len(users)))
                return users

        except Exception as e:
            print("[DATABASE ERROR] "
                  "get_all_active_users "
                  "failed: {}".format(e))
            return []

    # ============================================
    # FUNCTION 6: GET ALL USERS
    # ============================================

    async def get_all_users(self):
        await self._ensure_tables()
        try:
            async with self._get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM users"
                )
                rows = await cursor.fetchall()
                users = [dict(row) for row in rows]

                print("[DATABASE] Total users in "
                      "database: {}".format(len(users)))
                return users

        except Exception as e:
            print("[DATABASE ERROR] get_all_users "
                  "failed: {}".format(e))
            return []

    # ============================================
    # FUNCTION 7: UPDATE USER SUBSCRIPTION
    # ============================================

    async def update_user_subscription(
        self, chat_id, token, payment_id,
        expiry_date
    ):
        await self._ensure_tables()
        try:
            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            chat_id_str = str(chat_id)

            async with self._get_db() as db:
                await db.execute(
                    """
                    UPDATE users SET
                        is_active            = 1,
                        token                = ?,
                        token_activated_date = ?,
                        token_expiry_date    = ?,
                        locked_chat_id       = ?,
                        payment_id           = ?,
                        updated_at           = ?
                    WHERE chat_id = ?
                    """,
                    (
                        token, now, expiry_date,
                        chat_id_str, payment_id,
                        now, chat_id_str,
                    )
                )
                await db.commit()

                print("[DATABASE] ✅ Subscription "
                      "ACTIVATED | chat_id={} | "
                      "expires={}".format(
                          chat_id, expiry_date
                      ))
                return True

        except Exception as e:
            print("[DATABASE ERROR] "
                  "update_user_subscription failed "
                  "for {}: {}".format(chat_id, e))
            return False

    # ============================================
    # FUNCTION 8: DEACTIVATE USER
    # ============================================

    async def deactivate_user(self, chat_id):
        await self._ensure_tables()
        try:
            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            async with self._get_db() as db:
                await db.execute(
                    """
                    UPDATE users SET
                        is_active  = 0,
                        updated_at = ?
                    WHERE chat_id = ?
                    """,
                    (now, str(chat_id))
                )
                await db.commit()

                print("[DATABASE] ❌ User DEACTIVATED: "
                      "chat_id={}".format(chat_id))
                return True

        except Exception as e:
            print("[DATABASE ERROR] deactivate_user "
                  "failed for {}: {}".format(
                      chat_id, e
                  ))
            return False

    # ============================================
    # FUNCTION 9: IS USER ACTIVE
    # ============================================

    async def is_user_active(self, chat_id):
        await self._ensure_tables()
        try:
            user_data = None

            async with self._get_db() as db:
                cursor = await db.execute(
                    "SELECT is_active, "
                    "token_expiry_date "
                    "FROM users WHERE chat_id = ?",
                    (str(chat_id),)
                )
                row = await cursor.fetchone()
                if row:
                    user_data = dict(row)

            if not user_data:
                return False

            if not user_data["is_active"]:
                return False

            expiry = user_data["token_expiry_date"]

            if expiry:
                now_str = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if expiry < now_str:
                    await self.deactivate_user(chat_id)
                    print("[DATABASE] ⏰ Auto-deactivated "
                          "expired user: {}".format(
                              chat_id
                          ))
                    return False

            return True

        except Exception as e:
            print("[DATABASE ERROR] is_user_active "
                  "check failed for {}: {}".format(
                      chat_id, e
                  ))
            return False

    # ============================================
    # FUNCTION 10: INCREMENT SIGNAL COUNT
    # ============================================

    async def increment_signal_count(self, chat_id):
        await self._ensure_tables()
        try:
            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            async with self._get_db() as db:
                await db.execute(
                    """
                    UPDATE users SET
                        total_signals_received =
                            total_signals_received + 1,
                        last_signal_time       = ?,
                        updated_at             = ?
                    WHERE chat_id = ?
                    """,
                    (now, now, str(chat_id))
                )
                await db.commit()
                return True

        except Exception as e:
            print("[DATABASE ERROR] "
                  "increment_signal_count failed "
                  "for {}: {}".format(chat_id, e))
            return False

    # ============================================
    # FUNCTION 11: SAVE TOKEN
    # ============================================

    async def save_token(self, chat_id, token,
                         expiry_date):
        await self._ensure_tables()
        try:
            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            async with self._get_db() as db:
                await db.execute(
                    """
                    UPDATE users SET
                        token              = ?,
                        token_expiry_date  = ?,
                        updated_at         = ?
                    WHERE chat_id = ?
                    """,
                    (token, expiry_date, now,
                     str(chat_id))
                )
                await db.commit()

                print("[DATABASE] Token saved for "
                      "chat_id={}".format(chat_id))
                return True

        except Exception as e:
            print("[DATABASE ERROR] save_token "
                  "failed for {}: {}".format(
                      chat_id, e
                  ))
            return False

    # ============================================
    # FUNCTION 12: GET TOKEN INFO
    # ============================================

    async def get_token_info(self, token):
        await self._ensure_tables()
        try:
            async with self._get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM users "
                    "WHERE token = ?",
                    (token,)
                )
                row = await cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print("[DATABASE ERROR] get_token_info "
                  "failed: {}".format(e))
            return None

    # ============================================
    # FUNCTION 13: VALIDATE TOKEN
    # ============================================

    async def validate_token(self, token, chat_id):
        await self._ensure_tables()
        try:
            async with self._get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM users "
                    "WHERE token = ?",
                    (token,)
                )
                row = await cursor.fetchone()

                if not row:
                    print("[DATABASE] ⛔ Token "
                          "validation FAILED: "
                          "not found")
                    return False

                user = dict(row)

                expiry = user.get(
                    "token_expiry_date"
                )
                if expiry:
                    now_str = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if expiry < now_str:
                        print("[DATABASE] ⛔ Token "
                              "validation FAILED: "
                              "expired on "
                              "{}".format(expiry))
                        return False

                locked_id = user.get("locked_chat_id")

                if (locked_id is not None and
                        str(locked_id) !=
                        str(chat_id)):
                    print("[DATABASE] ⛔ Token "
                          "validation FAILED: "
                          "locked to different "
                          "chat_id")
                    return False

                print("[DATABASE] ✅ Token validation "
                      "PASSED for chat_id={}".format(
                          chat_id
                      ))
                return True

        except Exception as e:
            print("[DATABASE ERROR] validate_token "
                  "failed: {}".format(e))
            return False

    # ============================================
    # FUNCTION 14: LOCK TOKEN TO CHAT
    # ============================================

    async def lock_token_to_chat(self, token,
                                 chat_id):
        await self._ensure_tables()
        try:
            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            async with self._get_db() as db:
                await db.execute(
                    """
                    UPDATE users SET
                        locked_chat_id = ?,
                        updated_at     = ?
                    WHERE token = ?
                    """,
                    (str(chat_id), now, token)
                )
                await db.commit()

                print("[DATABASE] 🔒 Token LOCKED to "
                      "chat_id={}".format(chat_id))
                return True

        except Exception as e:
            print("[DATABASE ERROR] "
                  "lock_token_to_chat "
                  "failed: {}".format(e))
            return False

    # ============================================
    # FUNCTION 15: IS TOKEN EXPIRED
    # ============================================

    async def is_token_expired(self, token):
        await self._ensure_tables()
        try:
            async with self._get_db() as db:
                cursor = await db.execute(
                    "SELECT token_expiry_date "
                    "FROM users WHERE token = ?",
                    (token,)
                )
                row = await cursor.fetchone()

                if not row:
                    print("[DATABASE] Token not found "
                          "— treating as expired")
                    return True

                expiry = row["token_expiry_date"]

                if not expiry:
                    print("[DATABASE] Token has no "
                          "expiry — treating as "
                          "expired")
                    return True

                now_str = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                is_expired = expiry < now_str

                if is_expired:
                    print("[DATABASE] ⏰ Token "
                          "EXPIRED on: {}".format(
                              expiry
                          ))
                else:
                    print("[DATABASE] Token still "
                          "valid until: {}".format(
                              expiry
                          ))

                return is_expired

        except Exception as e:
            print("[DATABASE ERROR] "
                  "is_token_expired check "
                  "failed: {}".format(e))
            return True

    # ============================================
    # FUNCTION 16: GET EXPIRING USERS
    # ============================================

    async def get_expiring_users(self, days_left):
        await self._ensure_tables()
        try:
            now = datetime.now()
            now_str = now.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            future_str = (
                now + timedelta(days=days_left)
            ).strftime("%Y-%m-%d %H:%M:%S")

            async with self._get_db() as db:
                cursor = await db.execute(
                    """
                    SELECT * FROM users
                    WHERE is_active = 1
                      AND token_expiry_date
                          IS NOT NULL
                      AND token_expiry_date > ?
                      AND token_expiry_date <= ?
                    ORDER BY token_expiry_date ASC
                    """,
                    (now_str, future_str)
                )
                rows = await cursor.fetchall()
                users = [dict(row) for row in rows]

                print("[DATABASE] Users expiring "
                      "within {} days: {}".format(
                          days_left, len(users)
                      ))
                return users

        except Exception as e:
            print("[DATABASE ERROR] "
                  "get_expiring_users "
                  "failed: {}".format(e))
            return []
    # ============================================
    # FUNCTION 17: LOG SIGNAL
    # ============================================

    async def log_signal(self, pair, direction,
                         entry_price, target_1=None,
                         target_2=None,
                         stop_loss=None,
                         confidence=0.0,
                         sent_public=False,
                         sent_private=False):
        await self._ensure_tables()
        try:
            async with self._get_db() as db:
                cursor = await db.execute(
                    """
                    INSERT INTO signals_log
                        (pair, direction, entry_price,
                         target_1, target_2, stop_loss,
                         confidence, was_sent_public,
                         was_sent_private, result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                            'PENDING')
                    """,
                    (
                        pair,
                        direction.upper(),
                        entry_price,
                        target_1,
                        target_2,
                        stop_loss,
                        confidence,
                        1 if sent_public else 0,
                        1 if sent_private else 0,
                    )
                )
                await db.commit()

                signal_id = cursor.lastrowid

                print(
                    "[DATABASE] 📊 Signal #{} logged: "
                    "{} {} @ {:.4f} | "
                    "Confidence: {:.1f}%".format(
                        signal_id,
                        direction.upper(),
                        pair,
                        entry_price,
                        confidence,
                    )
                )
                return signal_id

        except Exception as e:
            print("[DATABASE ERROR] log_signal "
                  "failed for {} {}: {}".format(
                      direction, pair, e
                  ))
            return None

    # ============================================
    # FUNCTION 18: GET TODAY'S PUBLIC COUNT
    # ============================================

    async def get_today_public_count(self):
        await self._ensure_tables()
        try:
            today = datetime.now().strftime(
                "%Y-%m-%d"
            )

            async with self._get_db() as db:
                cursor = await db.execute(
                    "SELECT signals_sent_count FROM "
                    "public_channel_tracker "
                    "WHERE date = ?",
                    (today,)
                )
                row = await cursor.fetchone()

                count = (
                    row["signals_sent_count"]
                    if row else 0
                )
                return count

        except Exception as e:
            print("[DATABASE ERROR] "
                  "get_today_public_count "
                  "failed: {}".format(e))
            return 0

    # ============================================
    # FUNCTION 19: INCREMENT PUBLIC COUNT
    # ============================================

    async def increment_public_count(self):
        await self._ensure_tables()
        try:
            today = datetime.now().strftime(
                "%Y-%m-%d"
            )
            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            async with self._get_db() as db:
                await db.execute(
                    """
                    INSERT INTO public_channel_tracker
                        (date, signals_sent_count,
                         last_signal_time)
                    VALUES (?, 1, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        signals_sent_count =
                            signals_sent_count + 1,
                        last_signal_time   = ?
                    """,
                    (today, now, now)
                )
                await db.commit()

                new_count = (
                    await self.get_today_public_count()
                )
                print("[DATABASE] Public signal "
                      "count: {} for {}".format(
                          new_count, today
                      ))
                return True

        except Exception as e:
            print("[DATABASE ERROR] "
                  "increment_public_count "
                  "failed: {}".format(e))
            return False

    # ============================================
    # FUNCTION 20: CAN SEND PUBLIC
    # ============================================

    async def can_send_public(self):
        try:
            current_count = (
                await self.get_today_public_count()
            )
            limit = Config.PUBLIC_CHANNEL_DAILY_LIMIT
            can_send = current_count < limit

            print("[DATABASE] Public channel: "
                  "{}/{} signals sent today | "
                  "Can send: {}".format(
                      current_count, limit, can_send
                  ))
            return can_send

        except Exception as e:
            print("[DATABASE ERROR] can_send_public "
                  "failed: {}".format(e))
            return False

    # ============================================
    # FUNCTION 21: GET SIGNAL STATS
    # ============================================

    async def get_signal_stats(self):
        await self._ensure_tables()

        default_stats = {
            "total_signals": 0,
            "wins": 0,
            "losses": 0,
            "pending": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "avg_pnl": 0.0,
        }

        try:
            async with self._get_db() as db:
                cursor = await db.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN result = 'WIN'
                            THEN 1 ELSE 0 END)
                            as wins,
                        SUM(CASE WHEN result = 'LOSS'
                            THEN 1 ELSE 0 END)
                            as losses,
                        SUM(CASE
                            WHEN result = 'PENDING'
                            OR result IS NULL
                            THEN 1 ELSE 0
                        END) as pending,
                        AVG(CASE
                            WHEN pnl_percent
                                IS NOT NULL
                            THEN pnl_percent
                        END) as avg_pnl
                    FROM signals_log
                """)
                row = await cursor.fetchone()

                if not row or row["total"] == 0:
                    print("[DATABASE] Signal stats: "
                          "no signals recorded yet")
                    return default_stats

                total = row["total"]
                wins = row["wins"] or 0
                losses = row["losses"] or 0
                pending = row["pending"] or 0
                avg_pnl = row["avg_pnl"] or 0.0

                completed = wins + losses

                if completed > 0:
                    win_rate = round(
                        (wins / completed) * 100, 2
                    )
                    loss_rate = round(
                        (losses / completed) * 100, 2
                    )
                else:
                    win_rate = 0.0
                    loss_rate = 0.0

                avg_pnl = round(avg_pnl, 2)

                stats = {
                    "total_signals": total,
                    "wins": wins,
                    "losses": losses,
                    "pending": pending,
                    "win_rate": win_rate,
                    "loss_rate": loss_rate,
                    "avg_pnl": avg_pnl,
                }

                print(
                    "[DATABASE] 📈 Stats: {} signals "
                    "| {}W / {}L / {}P | "
                    "Win rate: {}% | "
                    "Avg PnL: {}%".format(
                        total, wins, losses,
                        pending, win_rate, avg_pnl,
                    )
                )
                return stats

        except Exception as e:
            print("[DATABASE ERROR] get_signal_stats "
                  "failed: {}".format(e))
            return default_stats

    # ============================================
    # FUNCTION 22: UPDATE SIGNAL SENT STATUS
    # ============================================

    async def update_signal_sent_status(
        self, signal_id, sent_public=False,
        sent_private=False
    ):
        """
        Update signal record with send status.

        Args:
            signal_id (int):      Signal row ID
            sent_public (bool):   Sent to public
            sent_private (bool):  Sent to private

        Returns:
            bool: True if updated
        """
        await self._ensure_tables()
        try:
            if signal_id is None:
                return False

            async with self._get_db() as db:
                await db.execute(
                    """
                    UPDATE signals_log
                    SET was_sent_public = ?,
                        was_sent_private = ?
                    WHERE id = ?
                    """,
                    (
                        1 if sent_public else 0,
                        1 if sent_private else 0,
                        signal_id,
                    )
                )
                await db.commit()

                print("[DATABASE] Signal #{} status "
                      "updated: public={} "
                      "private={}".format(
                          signal_id,
                          sent_public,
                          sent_private,
                      ))
                return True

        except Exception as e:
            print("[DATABASE] ⚠️ Update signal "
                  "status error: {}".format(e))
            return False

    # ============================================
    # AUTH BRIDGE METHODS
    # ============================================
    # These methods exist because auth.py calls
    # these exact names. They map to existing
    # methods or provide thin wrappers.
    # ============================================

    async def get_token(self, token):
        """
        Get token data by token string.
        Called by: auth.py
        Maps to: get_token_info()
        """
        return await self.get_token_info(token)

    async def create_token(self, token, days=28):
        """
        Create a placeholder user with this token.
        Called by: auth.py when generating tokens.
        """
        await self._ensure_tables()
        try:
            now = datetime.now()
            expiry = (
                now + timedelta(days=days)
            ).strftime("%Y-%m-%d %H:%M:%S")
            now_str = now.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            async with self._get_db() as database:
                # Check if token already exists
                cursor = await database.execute(
                    "SELECT id FROM users "
                    "WHERE token = ?",
                    (token,)
                )
                exists = await cursor.fetchone()

                if not exists:
                    await database.execute(
                        """
                        INSERT OR IGNORE INTO users
                            (chat_id, token,
                             token_expiry_date,
                             created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            "pending_{}".format(
                                token[-8:]
                            ),
                            token,
                            expiry,
                            now_str,
                        )
                    )
                    await database.commit()

                print("[DATABASE] Token created: "
                      "{}****".format(token[:12]))
                return True

        except Exception as e:
            print("[DATABASE] ⚠️ create_token "
                  "error: {}".format(e))
            return False

    async def activate_token(self, token, chat_id):
        """
        Activate a token and lock it to chat_id.
        Called by: auth.py

        FIX: Pending row is now deleted FIRST
        to prevent UNIQUE constraint violation
        on the token column.
        """
        await self._ensure_tables()
        try:
            now = datetime.now()
            now_str = now.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            expiry = (
                now + timedelta(
                    days=Config.SUBSCRIPTION_DAYS
                )
            ).strftime("%Y-%m-%d %H:%M:%S")
            chat_str = str(chat_id)

            async with self._get_db() as database:

                # ── STEP 1: Delete pending row FIRST ──
                # This prevents UNIQUE constraint
                # violation when we set token on
                # the real user row
                await database.execute(
                    """
                    DELETE FROM users
                    WHERE token = ?
                    AND chat_id LIKE 'pending_%'
                    """,
                    (token,)
                )

                # ── STEP 2: Check if user exists ──
                cursor = await database.execute(
                    "SELECT id FROM users "
                    "WHERE chat_id = ?",
                    (chat_str,)
                )
                user_exists = await cursor.fetchone()

                if user_exists:
                    # ── STEP 3A: Update existing ──
                    await database.execute(
                        """
                        UPDATE users SET
                            is_active = 1,
                            token = ?,
                            token_activated_date = ?,
                            token_expiry_date = ?,
                            locked_chat_id = ?,
                            updated_at = ?
                        WHERE chat_id = ?
                        """,
                        (
                            token, now_str, expiry,
                            chat_str, now_str,
                            chat_str,
                        )
                    )
                else:
                    # ── STEP 3B: Insert new user ──
                    await database.execute(
                        """
                        INSERT INTO users
                            (chat_id, is_active,
                             token,
                             token_activated_date,
                             token_expiry_date,
                             locked_chat_id,
                             created_at, updated_at)
                        VALUES
                            (?, 1, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chat_str, token,
                            now_str, expiry,
                            chat_str, now_str,
                            now_str,
                        )
                    )

                await database.commit()

                print("[DATABASE] ✅ Token activated "
                      "for chat_id={}".format(
                          chat_id
                      ))
                return True

        except Exception as e:
            print("[DATABASE] ⚠️ activate_token "
                  "error: {}".format(e))
            return False

    async def is_subscribed(self, chat_id):
        """
        Check if user has active subscription.
        Called by: auth.py
        Maps to: is_user_active()
        """
        return await self.is_user_active(chat_id)

    async def get_subscription(self, chat_id):
        """
        Get subscription data for a user.
        Called by: auth.py, signal_sender.py
        """
        user = await self.get_user(chat_id)
        if not user:
            return None

        return {
            "chat_id": user.get("chat_id"),
            "token": user.get("token"),
            "start_date": user.get(
                "token_activated_date"
            ),
            "end_date": user.get(
                "token_expiry_date"
            ),
            "is_active": user.get("is_active"),
            "payment_id": user.get("payment_id"),
        }

    async def deactivate_token(self, token):
        """
        Deactivate a token.
        Called by: auth.py
        """
        await self._ensure_tables()
        try:
            now = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            async with self._get_db() as database:
                await database.execute(
                    """
                    UPDATE users SET
                        is_active = 0,
                        updated_at = ?
                    WHERE token = ?
                    """,
                    (now, token)
                )
                await database.commit()

                print("[DATABASE] Token deactivated: "
                      "{}****".format(token[:12]))
                return True

        except Exception as e:
            print("[DATABASE] ⚠️ deactivate_token "
                  "error: {}".format(e))
            return False

    async def get_active_subscribers(self):
        """
        Get list of active subscriber chat_ids.
        Called by: signal_sender.py
        Returns: list of int chat_ids
        """
        users = await self.get_all_active_users()
        result = []
        for u in users:
            try:
                cid = int(u.get("chat_id", 0))
                if cid > 0:
                    result.append(cid)
            except (ValueError, TypeError):
                pass
        return result

    async def get_signal_count(self, chat_id):
        """
        Get total signals received by a user.
        Called by: telegram_bot.py, reminders.py
        """
        await self._ensure_tables()
        try:
            async with self._get_db() as database:
                cursor = await database.execute(
                    "SELECT total_signals_received "
                    "FROM users WHERE chat_id = ?",
                    (str(chat_id),)
                )
                row = await cursor.fetchone()

                if row:
                    return (
                        row["total_signals_received"]
                        or 0
                    )
                return 0

        except Exception as e:
            print("[DATABASE] ⚠️ get_signal_count "
                  "error: {}".format(e))
            return 0

    async def get_all_subscriptions(self):
        """
        Get all users with active subscriptions.
        Called by: reminders.py
        Returns list of subscription dicts.
        """
        await self._ensure_tables()
        try:
            async with self._get_db() as database:
                cursor = await database.execute(
                    """
                    SELECT chat_id, token,
                           token_activated_date,
                           token_expiry_date,
                           is_active, payment_id
                    FROM users
                    WHERE is_active = 1
                    AND token IS NOT NULL
                    """
                )
                rows = await cursor.fetchall()

                result = []
                for row in rows:
                    r = dict(row)
                    result.append({
                        "chat_id": r.get("chat_id"),
                        "token": r.get("token"),
                        "start_date": r.get(
                            "token_activated_date"
                        ),
                        "end_date": r.get(
                            "token_expiry_date"
                        ),
                        "is_active": r.get(
                            "is_active"
                        ),
                        "payment_id": r.get(
                            "payment_id"
                        ),
                    })

                return result

        except Exception as e:
            print("[DATABASE] ⚠️ "
                  "get_all_subscriptions "
                  "error: {}".format(e))
            return []


# ==================================================
# MODULE-LEVEL SINGLETON INSTANCE
# ==================================================

db = DatabaseManager()

print("[DATABASE] ✅ Database module loaded and ready")
print("[DATABASE] Call 'await db.create_tables()' "
      "at bot startup")         