# ============================================
# CRYPTO SIGNAL BOT - LOGGING & PERFORMANCE
# ============================================
# Centralized logging and signal performance
# tracking system.
#
# LOGGING:
#   - File: bot_logs.log (rotating, 10MB, 5 backups)
#   - Console: colored output by level
#   - Format: [TIMESTAMP] [LEVEL] [MODULE] - Message
#   - Specialized loggers for signals, users,
#     API calls, payments, and errors
#
# PERFORMANCE TRACKING:
#   - CSV file: signals_history.csv
#   - Every signal logged with full details
#   - Win/loss tracking after signal expiry
#   - Per-pair statistics
#   - Win rate calculation
#   - Performance reports
#
# Usage:
#   from utils.logger import bot_logger, performance_tracker
#   bot_logger.info("Signal generated", module="ENGINE")
#   performance_tracker.log_new_signal(signal_data)
# ============================================

import os
import csv
import uuid
import logging
import logging.handlers
import traceback
from datetime import datetime, timedelta
from collections import defaultdict

from config.settings import Config

# ============================================
# CONSTANTS
# ============================================

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)-12s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# File paths
try:
    LOG_DIR = os.path.dirname(Config.LOG_FILE_PATH)
    LOG_FILE = Config.LOG_FILE_PATH
except AttributeError:
    LOG_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "utils"
    )
    LOG_FILE = os.path.join(LOG_DIR, "bot_logs.log")

SIGNALS_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "signals_history.csv"
)

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(SIGNALS_CSV), exist_ok=True)

# Log file limits
MAX_LOG_BYTES = 10 * 1024 * 1024   # 10 MB
BACKUP_COUNT = 5

# Console colors (ANSI codes)
COLORS = {
    "DEBUG": "\033[36m",      # Cyan
    "INFO": "\033[32m",       # Green
    "WARNING": "\033[33m",    # Yellow
    "ERROR": "\033[31m",      # Red
    "CRITICAL": "\033[1;31m", # Bold Red
    "RESET": "\033[0m",       # Reset
    "BOLD": "\033[1m",        # Bold
    "DIM": "\033[2m",         # Dim
}

# CSV columns for signal history
CSV_COLUMNS = [
    "signal_id",
    "timestamp",
    "pair",
    "direction",
    "entry_price",
    "target_1",
    "target_2",
    "stop_loss",
    "confidence",
    "agreement_level",
    "risk_reward",
    "result",
    "pnl_percent",
    "result_timestamp",
    "notes",
]


# ============================================
# COLORED CONSOLE FORMATTER
# ============================================

class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds ANSI color codes
    to console log output.

    Colors:
    - DEBUG:    Cyan
    - INFO:     Green
    - WARNING:  Yellow
    - ERROR:    Red
    - CRITICAL: Bold Red

    Timestamp is dimmed, level is colored,
    module name is bold.
    """

    def format(self, record):
        """Format log record with colors."""
        try:
            level = record.levelname
            color = COLORS.get(level, "")
            reset = COLORS["RESET"]
            dim = COLORS["DIM"]
            bold = COLORS["BOLD"]

            # Build colored format
            timestamp = datetime.now().strftime(LOG_DATE_FORMAT)

            colored_msg = (
                "{dim}[{ts}]{reset} "
                "{color}[{level:<8}]{reset} "
                "{bold}[{name:<12}]{reset} "
                "{msg}"
            ).format(
                dim=dim,
                ts=timestamp,
                reset=reset,
                color=color,
                level=level,
                bold=bold,
                name=record.name[:12],
                msg=record.getMessage(),
            )

            return colored_msg

        except Exception:
            return super().format(record)


# ============================================
# LOGGER SETUP FUNCTION
# ============================================

def setup_logger(name="crypto_bot"):
    """
    Create and configure a logger instance.

    Sets up two handlers:
    1. RotatingFileHandler → bot_logs.log
       - Max 10MB per file
       - Keeps 5 backup files
       - All levels (DEBUG+)
       - Standard format

    2. StreamHandler → console
       - Colored output
       - INFO level and above
       - Colored format

    Args:
        name (str): Logger name (module identifier)

    Returns:
        logging.Logger: Configured logger instance
    """
    try:
        logger = logging.getLogger(name)

        # Avoid duplicate handlers
        if logger.handlers:
            return logger

        logger.setLevel(logging.DEBUG)

        # ------ File Handler (rotating) ------
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                LOG_FILE,
                maxBytes=MAX_LOG_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                LOG_FORMAT, datefmt=LOG_DATE_FORMAT
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print("[LOGGER] ⚠️ File handler failed: {}".format(e))

        # ------ Console Handler (colored) ------
        try:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = ColoredFormatter()
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        except Exception as e:
            print("[LOGGER] ⚠️ Console handler failed: {}".format(e))

        return logger

    except Exception as e:
        print("[LOGGER] ❌ Setup failed: {}".format(e))
        return logging.getLogger(name)


# ============================================
# BOT LOGGER CLASS
# ============================================

class BotLogger:
    """
    Centralized logging system for the crypto bot.

    Wraps Python's logging module with specialized
    methods for different event types:
    - Signal events
    - User actions
    - API calls
    - Payment events
    - Error reporting

    Each method formats the message consistently
    and routes to the appropriate log level.

    Attributes:
        _logger (Logger):     Main logger instance
        _signal_logger:       Signal-specific logger
        _user_logger:         User action logger
        _api_logger:          API call logger
        _payment_logger:      Payment event logger
        _error_logger:        Error logger
    """

    def __init__(self):
        """
        Initialize all logger instances.

        Creates separate loggers for each category
        so they can be filtered independently in
        the log file.
        """
        self._logger = setup_logger("crypto_bot")
        self._signal_logger = setup_logger("signal")
        self._user_logger = setup_logger("user")
        self._api_logger = setup_logger("api")
        self._payment_logger = setup_logger("payment")
        self._error_logger = setup_logger("error")

        self._log_count = {
            "debug": 0,
            "info": 0,
            "warning": 0,
            "error": 0,
            "critical": 0,
        }

        print("[LOGGER] ✅ BotLogger initialized")
        print("[LOGGER]    Log file: {}".format(LOG_FILE))
        print("[LOGGER]    Max size: {} MB × {} files".format(
            MAX_LOG_BYTES // (1024 * 1024), BACKUP_COUNT
        ))

    # ============================================
    # STANDARD LOG METHODS
    # ============================================

    def debug(self, message, module="BOT"):
        """Log DEBUG level message."""
        try:
            self._logger.debug("[{}] {}".format(module, message))
            self._log_count["debug"] += 1
        except Exception:
            pass

    def info(self, message, module="BOT"):
        """Log INFO level message."""
        try:
            self._logger.info("[{}] {}".format(module, message))
            self._log_count["info"] += 1
        except Exception:
            pass

    def warning(self, message, module="BOT"):
        """Log WARNING level message."""
        try:
            self._logger.warning("[{}] {}".format(module, message))
            self._log_count["warning"] += 1
        except Exception:
            pass

    def error(self, message, module="BOT"):
        """Log ERROR level message."""
        try:
            self._logger.error("[{}] {}".format(module, message))
            self._log_count["error"] += 1
        except Exception:
            pass

    def critical(self, message, module="BOT"):
        """Log CRITICAL level message."""
        try:
            self._logger.critical("[{}] {}".format(module, message))
            self._log_count["critical"] += 1
        except Exception:
            pass

    # ============================================
    # SPECIALIZED LOG METHODS
    # ============================================

    def log_signal(self, signal_data):
        """
        Log a trading signal with formatted details.

        Creates a structured multi-line log entry
        with all signal parameters.

        Args:
            signal_data (dict): Signal from engine
                Expected keys: pair, direction, confidence,
                entry_price, target_1, stop_loss
        """
        try:
            pair = signal_data.get("pair", "?")
            direction = signal_data.get("direction", "?")
            confidence = signal_data.get("confidence", 0)
            entry = signal_data.get("entry_price", 0)
            target_1 = signal_data.get("target_1", 0)
            target_2 = signal_data.get("target_2", 0)
            stop_loss = signal_data.get("stop_loss", 0)
            agreement = signal_data.get("agreement_level", "?")
            rr = signal_data.get("risk_reward", 0)

            msg = (
                "SIGNAL | {pair} {dir} | "
                "Conf: {conf:.0f}% | "
                "Entry: {entry} | "
                "T1: {t1} | T2: {t2} | "
                "SL: {sl} | "
                "Agree: {agree} | "
                "R/R: {rr:.2f}"
            ).format(
                pair=pair,
                dir=direction,
                conf=confidence,
                entry=entry,
                t1=target_1,
                t2=target_2,
                sl=stop_loss,
                agree=agreement,
                rr=rr if rr else 0,
            )

            self._signal_logger.info(msg)
            self._log_count["info"] += 1

        except Exception as e:
            self._logger.error(
                "Signal log error: {}".format(e)
            )

    def log_user_action(self, chat_id, action, details=""):
        """
        Log a user action.

        Actions include: registered, activated_token,
        checked_status, requested_help, etc.

        Args:
            chat_id (int):   User's chat ID
            action (str):    Action name
            details (str):   Additional details
        """
        try:
            msg = "USER | chat:{} | {} | {}".format(
                chat_id, action, details
            )
            self._user_logger.info(msg)
            self._log_count["info"] += 1

        except Exception as e:
            self._logger.error(
                "User log error: {}".format(e)
            )

    def log_api_call(self, endpoint, status, response_time_ms,
                     details=""):
        """
        Log an API call with response metrics.

        Args:
            endpoint (str):        API endpoint/URL
            status (str):          "SUCCESS" or "FAILED"
            response_time_ms (float): Response time in ms
            details (str):         Additional info
        """
        try:
            msg = "API | {} | {} | {:.0f}ms | {}".format(
                endpoint, status, response_time_ms, details
            )

            if status == "SUCCESS":
                self._api_logger.info(msg)
            elif response_time_ms > 5000:
                self._api_logger.warning(
                    msg + " | SLOW RESPONSE"
                )
            else:
                self._api_logger.error(msg)

            self._log_count["info"] += 1

        except Exception as e:
            self._logger.error(
                "API log error: {}".format(e)
            )

    def log_error(self, module, error, tb_info=None):
        """
        Log an error with optional traceback.

        Captures the full exception chain for
        debugging.

        Args:
            module (str):    Module where error occurred
            error:           Exception object or string
            tb_info:         Traceback info (optional)
        """
        try:
            msg = "ERROR in [{}]: {}".format(module, error)

            if tb_info:
                if isinstance(tb_info, str):
                    tb_str = tb_info
                else:
                    tb_str = traceback.format_exc()
                msg += "\n  Traceback:\n  {}".format(
                    tb_str.replace("\n", "\n  ")
                )

            self._error_logger.error(msg)
            self._log_count["error"] += 1

        except Exception:
            try:
                self._logger.error(
                    "Error logging failed: {}".format(error)
                )
            except Exception:
                pass

    def log_payment(self, chat_id, payment_id, amount, status):
        """
        Log a payment event.

        Args:
            chat_id (int):     User's chat ID
            payment_id (str):  Payment reference
            amount (float):    Payment amount
            status (str):      "SUCCESS", "FAILED", "PENDING"
        """
        try:
            msg = (
                "PAYMENT | chat:{} | pay_id:{} | "
                "₹{} | {}"
            ).format(
                chat_id, payment_id, amount, status
            )

            if status == "SUCCESS":
                self._payment_logger.info(msg)
            elif status == "FAILED":
                self._payment_logger.error(msg)
            else:
                self._payment_logger.warning(msg)

            self._log_count["info"] += 1

        except Exception as e:
            self._logger.error(
                "Payment log error: {}".format(e)
            )

    def log_brain_result(self, brain_name, result):
        """
        Log individual brain analysis result.

        Args:
            brain_name (str):  Brain identifier
            result (dict):     Brain output
        """
        try:
            direction = result.get("direction", "?")
            confidence = result.get("confidence", 0)
            score = result.get("score", "?")

            msg = "BRAIN | {} | Dir: {} | Conf: {} | Score: {}".format(
                brain_name, direction, confidence, score
            )
            self._signal_logger.debug(msg)

        except Exception:
            pass

    def log_startup(self, version="1.0.0"):
        """Log bot startup with system info."""
        try:
            msg = (
                "\n"
                "{'='*50}\n"
                "  CRYPTO SIGNAL BOT STARTED\n"
                "  Version: {}\n"
                "  Time: {}\n"
                "  Log File: {}\n"
                "  CSV File: {}\n"
                "{'='*50}"
            ).format(
                version,
                datetime.now().strftime(DATE_FORMAT),
                LOG_FILE,
                SIGNALS_CSV,
            )
            self._logger.info(msg)
        except Exception:
            pass

    def log_shutdown(self, reason="normal"):
        """Log bot shutdown."""
        try:
            stats = self.get_log_stats()
            msg = (
                "BOT SHUTDOWN | Reason: {} | "
                "Logs: D:{} I:{} W:{} E:{} C:{}".format(
                    reason,
                    stats["debug"],
                    stats["info"],
                    stats["warning"],
                    stats["error"],
                    stats["critical"],
                )
            )
            self._logger.info(msg)
        except Exception:
            pass

    # ============================================
    # STATISTICS
    # ============================================

    def get_log_stats(self):
        """
        Get log count statistics.

        Returns:
            dict: Count of each log level
        """
        return dict(self._log_count)

    def get_log_file_size(self):
        """
        Get current log file size in MB.

        Returns:
            float: File size in MB
        """
        try:
            if os.path.exists(LOG_FILE):
                size = os.path.getsize(LOG_FILE)
                return round(size / (1024 * 1024), 2)
            return 0.0
        except Exception:
            return 0.0


# ============================================
# PERFORMANCE TRACKER CLASS
# ============================================

class PerformanceTracker:
    """
    Signal performance tracking and analysis.

    Records every signal to a CSV file and provides
    methods to update results and generate reports.

    CSV file: signals_history.csv
    Updated: When signals are generated and when
             results are determined.

    Tracks:
    - Win/loss/pending counts
    - Per-pair statistics
    - PnL percentages
    - Best/worst performing pairs
    - Overall win rate

    Attributes:
        csv_path (str):           Path to CSV file
        _signals (dict):          In-memory signal store
        _results (dict):          Signal results
        _pair_stats (defaultdict): Per-pair counters
    """

    def __init__(self):
        """
        Initialize Performance Tracker.

        Creates CSV file with headers if it doesn't
        exist. Loads existing signals from CSV for
        statistics.
        """
        self.csv_path = SIGNALS_CSV

        # In-memory signal store
        # {signal_id: signal_data}
        self._signals = {}

        # Per-pair statistics
        # {pair: {"wins": 0, "losses": 0, "total_pnl": 0.0, ...}}
        self._pair_stats = defaultdict(lambda: {
            "wins": 0,
            "losses": 0,
            "pending": 0,
            "total_pnl": 0.0,
            "total_signals": 0,
            "avg_confidence": 0.0,
            "confidence_sum": 0.0,
        })

        # Global counters
        self._total_wins = 0
        self._total_losses = 0
        self._total_pending = 0
        self._total_pnl = 0.0

        # Initialize CSV
        self._init_csv()

        # Load existing data
        self._load_existing_signals()

        print("[PERF] ✅ Performance Tracker initialized")
        print("[PERF]    CSV: {}".format(self.csv_path))
        print("[PERF]    Existing signals: {}".format(
            len(self._signals)
        ))

    def _init_csv(self):
        """
        Create CSV file with headers if it doesn't exist.

        Headers match CSV_COLUMNS constant.
        """
        try:
            if not os.path.exists(self.csv_path):
                with open(self.csv_path, "w", newline="",
                          encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f, fieldnames=CSV_COLUMNS
                    )
                    writer.writeheader()
                print("[PERF] 📄 CSV file created")
            else:
                print("[PERF] 📄 CSV file exists")

        except Exception as e:
            print("[PERF] ❌ CSV init error: {}".format(e))

    def _load_existing_signals(self):
        """
        Load existing signals from CSV into memory
        for statistics calculation.

        Rebuilds pair stats and global counters
        from historical data.
        """
        try:
            if not os.path.exists(self.csv_path):
                return

            with open(self.csv_path, "r", newline="",
                      encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        signal_id = row.get("signal_id", "")
                        if not signal_id:
                            continue

                        self._signals[signal_id] = row

                        pair = row.get("pair", "?")
                        result = row.get("result", "PENDING")
                        confidence = float(
                            row.get("confidence", 0) or 0
                        )

                        pnl_str = row.get("pnl_percent", "0")
                        try:
                            pnl = float(pnl_str) if pnl_str else 0.0
                        except (ValueError, TypeError):
                            pnl = 0.0

                        # Update pair stats
                        ps = self._pair_stats[pair]
                        ps["total_signals"] += 1
                        ps["confidence_sum"] += confidence

                        if result == "WIN":
                            ps["wins"] += 1
                            ps["total_pnl"] += pnl
                            self._total_wins += 1
                            self._total_pnl += pnl

                        elif result == "LOSS":
                            ps["losses"] += 1
                            ps["total_pnl"] += pnl
                            self._total_losses += 1
                            self._total_pnl += pnl

                        else:
                            ps["pending"] += 1
                            self._total_pending += 1

                    except Exception:
                        continue

            # Calculate averages
            for pair, ps in self._pair_stats.items():
                total = ps["total_signals"]
                if total > 0:
                    ps["avg_confidence"] = round(
                        ps["confidence_sum"] / total, 2
                    )

        except Exception as e:
            print("[PERF] ⚠️ Load existing error: {}".format(e))

    # ============================================
    # FUNCTION 1: LOG NEW SIGNAL
    # ============================================

    def log_new_signal(self, signal_data):
        """
        Record a new signal to CSV and memory.

        Generates a unique signal_id for tracking.
        Initial result is "PENDING" until updated.

        Args:
            signal_data (dict): Signal from engine
                Expected keys: pair, direction, confidence,
                entry_price, target_1, target_2, stop_loss

        Returns:
            str: Generated signal_id for future reference
        """
        try:
            signal_id = "SIG-{}".format(
                str(uuid.uuid4())[:8].upper()
            )

            now = datetime.now().strftime(DATE_FORMAT)

            row = {
                "signal_id": signal_id,
                "timestamp": now,
                "pair": signal_data.get("pair", "?"),
                "direction": signal_data.get("direction", "?"),
                "entry_price": signal_data.get("entry_price", 0),
                "target_1": signal_data.get("target_1", 0),
                "target_2": signal_data.get("target_2", 0),
                "stop_loss": signal_data.get("stop_loss", 0),
                "confidence": signal_data.get("confidence", 0),
                "agreement_level": signal_data.get(
                    "agreement_level", "?"
                ),
                "risk_reward": signal_data.get("risk_reward", 0),
                "result": "PENDING",
                "pnl_percent": "",
                "result_timestamp": "",
                "notes": "",
            }

            # Save to CSV
            self._append_to_csv(row)

            # Save to memory
            self._signals[signal_id] = row

            # Update pair stats
            pair = row["pair"]
            ps = self._pair_stats[pair]
            ps["total_signals"] += 1
            ps["pending"] += 1
            ps["confidence_sum"] += float(row["confidence"])

            total = ps["total_signals"]
            if total > 0:
                ps["avg_confidence"] = round(
                    ps["confidence_sum"] / total, 2
                )

            self._total_pending += 1

            print("[PERF] 📝 Signal logged: {} | {} {} | "
                  "{:.0f}%".format(
                      signal_id,
                      row["pair"],
                      row["direction"],
                      float(row["confidence"]),
                  ))

            return signal_id

        except Exception as e:
            print("[PERF] ❌ Log signal error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 2: UPDATE SIGNAL RESULT
    # ============================================

    def update_signal_result(self, signal_id, result,
                              pnl_percent=0.0, notes=""):
        """
        Update the result of a previously logged signal.

        Called when signal outcome is determined
        (target hit or stop loss hit).

        Args:
            signal_id (str):      Signal identifier
            result (str):         "WIN" or "LOSS"
            pnl_percent (float):  Profit/loss percentage
            notes (str):          Optional notes

        Returns:
            bool: True if updated successfully
        """
        try:
            result = result.upper()
            if result not in ("WIN", "LOSS"):
                print("[PERF] ⚠️ Invalid result: {} — "
                      "must be WIN or LOSS".format(result))
                return False

            # Update memory
            if signal_id in self._signals:
                signal = self._signals[signal_id]
                old_result = signal.get("result", "PENDING")

                signal["result"] = result
                signal["pnl_percent"] = str(pnl_percent)
                signal["result_timestamp"] = datetime.now().strftime(
                    DATE_FORMAT
                )
                signal["notes"] = notes

                pair = signal.get("pair", "?")
                ps = self._pair_stats[pair]

                # Remove from old category
                if old_result == "PENDING":
                    ps["pending"] = max(0, ps["pending"] - 1)
                    self._total_pending = max(
                        0, self._total_pending - 1
                    )
                elif old_result == "WIN":
                    ps["wins"] = max(0, ps["wins"] - 1)
                    self._total_wins = max(0, self._total_wins - 1)
                elif old_result == "LOSS":
                    ps["losses"] = max(0, ps["losses"] - 1)
                    self._total_losses = max(
                        0, self._total_losses - 1
                    )

                # Add to new category
                if result == "WIN":
                    ps["wins"] += 1
                    self._total_wins += 1
                else:
                    ps["losses"] += 1
                    self._total_losses += 1

                ps["total_pnl"] += pnl_percent
                self._total_pnl += pnl_percent

                # Rewrite CSV
                self._rewrite_csv()

                print("[PERF] {} Signal {} → {} | PnL: "
                      "{:+.2f}%".format(
                          "✅" if result == "WIN" else "❌",
                          signal_id, result, pnl_percent,
                      ))

                return True

            else:
                print("[PERF] ⚠️ Signal {} not found".format(
                    signal_id
                ))
                return False

        except Exception as e:
            print("[PERF] ❌ Update result error: {}".format(e))
            return False

    # ============================================
    # FUNCTION 3: WIN RATE
    # ============================================

    def get_win_rate(self):
        """
        Calculate overall win rate percentage.

        Only counts resolved signals (WIN + LOSS).
        Pending signals are excluded.

        Returns:
            float: Win rate as percentage (0-100),
                   or 0.0 if no resolved signals
        """
        try:
            total_resolved = self._total_wins + self._total_losses

            if total_resolved == 0:
                return 0.0

            return round(
                (self._total_wins / total_resolved) * 100, 2
            )

        except Exception:
            return 0.0

    # ============================================
    # FUNCTION 4: PERFORMANCE REPORT
    # ============================================

    def get_performance_report(self):
        """
        Generate comprehensive performance summary.

        Returns:
            dict: {
                "total_signals": int,
                "wins": int,
                "losses": int,
                "pending": int,
                "win_rate": float,
                "total_pnl": float,
                "avg_pnl_per_trade": float,
                "best_pair": str,
                "worst_pair": str,
                "pair_breakdown": dict,
                "report_time": str,
            }
        """
        try:
            total_signals = (
                self._total_wins +
                self._total_losses +
                self._total_pending
            )

            total_resolved = self._total_wins + self._total_losses

            avg_pnl = 0.0
            if total_resolved > 0:
                avg_pnl = round(
                    self._total_pnl / total_resolved, 2
                )

            best = self.get_best_pair()
            worst = self.get_worst_pair()

            # Pair breakdown
            pair_breakdown = {}
            for pair, ps in self._pair_stats.items():
                p_resolved = ps["wins"] + ps["losses"]
                p_wr = 0.0
                if p_resolved > 0:
                    p_wr = round(
                        (ps["wins"] / p_resolved) * 100, 2
                    )

                pair_breakdown[pair] = {
                    "total": ps["total_signals"],
                    "wins": ps["wins"],
                    "losses": ps["losses"],
                    "pending": ps["pending"],
                    "win_rate": p_wr,
                    "total_pnl": round(ps["total_pnl"], 2),
                    "avg_confidence": ps["avg_confidence"],
                }

            report = {
                "total_signals": total_signals,
                "wins": self._total_wins,
                "losses": self._total_losses,
                "pending": self._total_pending,
                "win_rate": self.get_win_rate(),
                "total_pnl": round(self._total_pnl, 2),
                "avg_pnl_per_trade": avg_pnl,
                "best_pair": best,
                "worst_pair": worst,
                "pair_breakdown": pair_breakdown,
                "report_time": datetime.now().strftime(
                    DATE_FORMAT
                ),
            }

            return report

        except Exception as e:
            print("[PERF] ❌ Report error: {}".format(e))
            return {
                "total_signals": 0,
                "wins": 0,
                "losses": 0,
                "pending": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl_per_trade": 0.0,
                "best_pair": "N/A",
                "worst_pair": "N/A",
                "pair_breakdown": {},
                "report_time": datetime.now().strftime(
                    DATE_FORMAT
                ),
            }

    # ============================================
    # FUNCTION 5: BEST PAIR
    # ============================================

    def get_best_pair(self):
        """
        Find the pair with the highest win rate.

        Requires at least 3 resolved signals to
        qualify (avoid single-trade statistics).

        Returns:
            str: Best pair name, or "N/A"
        """
        try:
            best_pair = "N/A"
            best_rate = -1.0

            for pair, ps in self._pair_stats.items():
                resolved = ps["wins"] + ps["losses"]
                if resolved < 3:
                    continue

                wr = ps["wins"] / resolved
                if wr > best_rate:
                    best_rate = wr
                    best_pair = pair

            if best_pair != "N/A" and best_rate >= 0:
                return "{} ({:.0f}%)".format(
                    best_pair, best_rate * 100
                )

            return best_pair

        except Exception:
            return "N/A"

    # ============================================
    # FUNCTION 6: WORST PAIR
    # ============================================

    def get_worst_pair(self):
        """
        Find the pair with the lowest win rate.

        Requires at least 3 resolved signals.

        Returns:
            str: Worst pair name, or "N/A"
        """
        try:
            worst_pair = "N/A"
            worst_rate = 2.0  # Above 100%

            for pair, ps in self._pair_stats.items():
                resolved = ps["wins"] + ps["losses"]
                if resolved < 3:
                    continue

                wr = ps["wins"] / resolved
                if wr < worst_rate:
                    worst_rate = wr
                    worst_pair = pair

            if worst_pair != "N/A" and worst_rate <= 1.0:
                return "{} ({:.0f}%)".format(
                    worst_pair, worst_rate * 100
                )

            return worst_pair

        except Exception:
            return "N/A"

    # ============================================
    # FUNCTION 7: PAIR WIN RATE
    # ============================================

    def get_pair_win_rate(self, pair):
        """
        Get win rate for a specific pair.

        Args:
            pair (str): Trading pair (e.g. "BTC/USDT")

        Returns:
            float: Win rate percentage, or 0.0
        """
        try:
            ps = self._pair_stats.get(pair)
            if not ps:
                return 0.0

            resolved = ps["wins"] + ps["losses"]
            if resolved == 0:
                return 0.0

            return round((ps["wins"] / resolved) * 100, 2)

        except Exception:
            return 0.0

    # ============================================
    # FUNCTION 8: RECENT SIGNALS
    # ============================================

    def get_recent_signals(self, limit=10):
        """
        Get the most recent signals.

        Args:
            limit (int): Maximum signals to return

        Returns:
            list[dict]: Recent signals newest first
        """
        try:
            signals = list(self._signals.values())

            # Sort by timestamp descending
            signals.sort(
                key=lambda x: x.get("timestamp", ""),
                reverse=True,
            )

            return signals[:limit]

        except Exception:
            return []

    # ============================================
    # FUNCTION 9: FORMATTED REPORT
    # ============================================

    def get_formatted_report(self):
        """
        Generate a human-readable performance report
        suitable for Telegram message.

        Returns:
            str: HTML-formatted report string
        """
        try:
            report = self.get_performance_report()

            msg = (
                "📊 <b>Signal Performance Report</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "📈 <b>Overall Stats</b>\n"
                "• Total signals: <b>{total}</b>\n"
                "• Wins: <b>{wins}</b> ✅\n"
                "• Losses: <b>{losses}</b> ❌\n"
                "• Pending: <b>{pending}</b> ⏳\n"
                "• Win rate: <b>{wr:.1f}%</b>\n"
                "• Total PnL: <b>{pnl:+.2f}%</b>\n"
                "• Avg PnL/trade: <b>{avg:+.2f}%</b>\n"
                "\n"
                "🏆 Best pair: <b>{best}</b>\n"
                "📉 Worst pair: <b>{worst}</b>\n"
            ).format(
                total=report["total_signals"],
                wins=report["wins"],
                losses=report["losses"],
                pending=report["pending"],
                wr=report["win_rate"],
                pnl=report["total_pnl"],
                avg=report["avg_pnl_per_trade"],
                best=report["best_pair"],
                worst=report["worst_pair"],
            )

            # Per-pair breakdown
            if report["pair_breakdown"]:
                msg += "\n━━━ <b>Per Pair</b> ━━━\n"

                for pair, stats in sorted(
                    report["pair_breakdown"].items()
                ):
                    msg += (
                        "• {pair}: {w}W/{l}L "
                        "({wr:.0f}%) | "
                        "PnL: {pnl:+.1f}%\n"
                    ).format(
                        pair=pair,
                        w=stats["wins"],
                        l=stats["losses"],
                        wr=stats["win_rate"],
                        pnl=stats["total_pnl"],
                    )

            msg += "\n⏰ <i>{}</i>".format(report["report_time"])

            return msg

        except Exception as e:
            return "📊 Performance report unavailable: {}".format(e)

    # ============================================
    # CSV HELPERS
    # ============================================

    def _append_to_csv(self, row_dict):
        """
        Append a single row to the CSV file.

        Args:
            row_dict (dict): Row data matching CSV_COLUMNS
        """
        try:
            with open(self.csv_path, "a", newline="",
                      encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=CSV_COLUMNS
                )
                writer.writerow(row_dict)

        except Exception as e:
            print("[PERF] ❌ CSV append error: {}".format(e))

    def _rewrite_csv(self):
        """
        Rewrite the entire CSV from memory.

        Called after updating signal results to
        ensure CSV reflects current state.
        """
        try:
            with open(self.csv_path, "w", newline="",
                      encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=CSV_COLUMNS
                )
                writer.writeheader()

                # Sort by timestamp
                sorted_signals = sorted(
                    self._signals.values(),
                    key=lambda x: x.get("timestamp", ""),
                )

                for signal in sorted_signals:
                    # Ensure all columns present
                    clean_row = {}
                    for col in CSV_COLUMNS:
                        clean_row[col] = signal.get(col, "")
                    writer.writerow(clean_row)

        except Exception as e:
            print("[PERF] ❌ CSV rewrite error: {}".format(e))

    def get_csv_row_count(self):
        """
        Get number of rows in CSV file.

        Returns:
            int: Row count (excluding header)
        """
        try:
            if not os.path.exists(self.csv_path):
                return 0

            with open(self.csv_path, "r", encoding="utf-8") as f:
                return max(0, sum(1 for _ in f) - 1)

        except Exception:
            return 0


# ==================================================
# MODULE-LEVEL SINGLETONS
# ==================================================

bot_logger = BotLogger()
performance_tracker = PerformanceTracker()

print("[LOGGER] ✅ Logging & Performance modules loaded")