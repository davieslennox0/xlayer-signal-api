"""
database.py — SQLite database for BTC Prediction Telegram Bot
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id     TEXT UNIQUE NOT NULL,
        telegram_name   TEXT,
        email           TEXT UNIQUE,
        wallet_address  TEXT,
        wallet_key      TEXT,
        balance         REAL DEFAULT 0.0,
        is_active       INTEGER DEFAULT 0,
        is_owner        INTEGER DEFAULT 0,
        joined_at       TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS trades (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER,
        direction       TEXT,
        amount          REAL,
        signal_score    REAL,
        confidence      REAL,
        market_id       INTEGER,
        outcome_id      INTEGER,
        status          TEXT DEFAULT 'pending',
        result          TEXT,
        pnl             REAL DEFAULT 0,
        fee_charged     REAL DEFAULT 0.1,
        tx_hash         TEXT,
        placed_at       TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS fees (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER,
        amount          REAL,
        trade_id        INTEGER,
        collected_at    TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS deposits (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER,
        tx_hash         TEXT UNIQUE,
        amount_usdc     REAL,
        verified        INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bypass_uses (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id     TEXT,
        used_at         TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()


# ── User helpers ──────────────────────────────────────────────────────────────
def get_user(telegram_id: str):
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE telegram_id = ?", (str(telegram_id),)
    ).fetchone()
    conn.close()
    return user


def create_user(telegram_id: str, name: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (telegram_id, telegram_name) VALUES (?, ?)",
        (str(telegram_id), name)
    )
    conn.commit()
    conn.close()


def update_user(telegram_id: str, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [str(telegram_id)]
    conn = get_conn()
    conn.execute(f"UPDATE users SET {fields} WHERE telegram_id = ?", values)
    conn.commit()
    conn.close()


def deduct_balance(telegram_id: str, amount: float) -> bool:
    conn = get_conn()
    user = conn.execute(
        "SELECT balance FROM users WHERE telegram_id = ?", (str(telegram_id),)
    ).fetchone()
    if not user or user["balance"] < amount:
        conn.close()
        return False
    conn.execute(
        "UPDATE users SET balance = balance - ? WHERE telegram_id = ?",
        (amount, str(telegram_id))
    )
    conn.commit()
    conn.close()
    return True


def add_balance(telegram_id: str, amount: float):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
        (amount, str(telegram_id))
    )
    conn.commit()
    conn.close()


def get_all_active_users():
    conn = get_conn()
    users = conn.execute(
        "SELECT * FROM users WHERE is_active = 1"
    ).fetchall()
    conn.close()
    return users


# ── Trade helpers ─────────────────────────────────────────────────────────────
def log_trade(user_id, direction, amount, confidence, market_id, outcome_id, tx_hash):
    conn = get_conn()
    c = conn.execute(
        """INSERT INTO trades
           (user_id, direction, amount, confidence, market_id, outcome_id, tx_hash, fee_charged)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0.1)""",
        (user_id, direction, amount, confidence, market_id, outcome_id, tx_hash)
    )
    trade_id = c.lastrowid
    conn.commit()
    conn.close()
    return trade_id


def get_user_trades(user_id: int, limit=10):
    conn = get_conn()
    trades = conn.execute(
        "SELECT * FROM trades WHERE user_id = ? ORDER BY placed_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return trades


def get_user_stats(user_id: int):
    conn = get_conn()
    stats = conn.execute("""
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
            SUM(pnl) as total_pnl,
            SUM(fee_charged) as total_fees,
            SUM(amount) as total_volume
        FROM trades WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    return stats


# ── Fee helpers ───────────────────────────────────────────────────────────────
def log_fee(user_id: int, amount: float, trade_id: int):
    conn = get_conn()
    conn.execute(
        "INSERT INTO fees (user_id, amount, trade_id) VALUES (?, ?, ?)",
        (user_id, amount, trade_id)
    )
    conn.commit()
    conn.close()


def get_total_fees():
    conn = get_conn()
    result = conn.execute("SELECT SUM(amount) as total FROM fees").fetchone()
    conn.close()
    return result["total"] or 0.0


# ── Admin stats ───────────────────────────────────────────────────────────────
def get_admin_stats():
    conn = get_conn()
    stats = {
        "total_users":   conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "active_users":  conn.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0],
        "total_trades":  conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0],
        "total_volume":  conn.execute("SELECT COALESCE(SUM(amount),0) FROM trades").fetchone()[0],
        "total_fees":    conn.execute("SELECT COALESCE(SUM(amount),0) FROM fees").fetchone()[0],
        "today_trades":  conn.execute(
            "SELECT COUNT(*) FROM trades WHERE DATE(placed_at) = DATE('now')"
        ).fetchone()[0],
        "today_volume":  conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM trades WHERE DATE(placed_at) = DATE('now')"
        ).fetchone()[0],
    }
    conn.close()
    return stats


# ── Bypass helpers ────────────────────────────────────────────────────────────
def count_bypass_uses():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM bypass_uses").fetchone()[0]
    conn.close()
    return count


def log_bypass_use(telegram_id: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO bypass_uses (telegram_id) VALUES (?)", (str(telegram_id),)
    )
    conn.commit()
    conn.close()


# ── Deposit helpers ───────────────────────────────────────────────────────────
def log_deposit(user_id: int, tx_hash: str, amount: float):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO deposits (user_id, tx_hash, amount_usdc, verified) VALUES (?, ?, ?, 1)",
        (user_id, tx_hash, amount)
    )
    conn.commit()
    conn.close()


def tx_already_used(tx_hash: str) -> bool:
    conn = get_conn()
    result = conn.execute(
        "SELECT id FROM deposits WHERE tx_hash = ?", (tx_hash,)
    ).fetchone()
    conn.close()
    return result is not None
