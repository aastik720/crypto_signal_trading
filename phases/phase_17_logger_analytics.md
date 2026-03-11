PROMPT FOR PHASE 13:
====================

Project: CryptoSignal Bot (continuing from Phase 1-12)
Task: Build logging system in utils/logger.py

CONTEXT: We need to log EVERYTHING for debugging and 
performance tracking. Also need to track signal win/loss rate.

BUILD utils/logger.py with these EXACT specifications:

USE Python's built-in logging module.

SETUP:
- Log to file: bot_logs.log (rotating, max 10MB, keep 5 files)
- Log to console: with colors for different levels
- Log format: [TIMESTAMP] [LEVEL] [MODULE] - Message

LOG LEVELS:
- DEBUG: Detailed algorithm calculations
- INFO: Normal operations (signal generated, user registered)
- WARNING: Non-critical issues (rate limit approaching)
- ERROR: Failures (API error, database error)
- CRITICAL: Bot-breaking issues

CREATE THESE LOGGER FUNCTIONS:

1. setup_logger(name) - creates and configures logger
2. log_signal(signal_data) - special formatted signal log
3. log_user_action(chat_id, action, details) - user actions
4. log_api_call(endpoint, status, response_time) - API calls
5. log_error(module, error, traceback_info) - errors
6. log_payment(chat_id, payment_id, amount, status) - payments

SIGNAL PERFORMANCE TRACKER:
- Track every signal in a separate CSV file: signals_history.csv
- Columns: timestamp, pair, direction, entry, target1, target2,
  stoploss, confidence, result, pnl_percent
- Function to update signal result (WIN/LOSS) after time passes
- Function to calculate overall win rate
- Function to generate performance report

CLASS: PerformanceTracker
1. log_new_signal(signal)
2. update_signal_result(signal_id, result, pnl)
3. get_win_rate() - returns percentage
4. get_performance_report() - returns summary dict
5. get_best_pair() - which pair has best win rate
6. get_worst_pair() - which pair has worst win rate

Full working code. Production-ready.