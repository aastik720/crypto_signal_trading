# ============================================
# DATABASE PACKAGE INITIALIZER
# ============================================
# This package manages the SQLite database
# for users, subscriptions, and signals.
#
# Usage:
#   from database.db_manager import db
#   await db.create_tables()
#   await db.add_user(...)
# ============================================

from database.db_manager import db