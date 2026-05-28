"""
Edge IoT Discord Bot Framework — 資料庫抽象層
提供：SQLite 實作（開發用），未來可無痛切換 PostgreSQL
"""

import os
import json
import sqlite3
import logging
from typing import Any

log = logging.getLogger(__name__)

# 從環境變數決定資料庫類型
DB_TYPE = os.environ.get("DB_TYPE", "sqlite")  # sqlite | json (後備)
DB_PATH = os.environ.get("DB_PATH", "data.db")


class Database:
    """
    統一的資料庫介面。
    目前實作為 SQLite，但外部呼叫者不需知道底層。
    未來若要換 PostgreSQL，只需改此類別，不需動任何 Cog。
    """

    def __init__(self):
        self._conn: sqlite3.Connection | None = None
        self._connected = False

    # ── 生命週期 ──

    def connect(self):
        """建立資料庫連線並初始化表格。"""
        if self._connected:
            return
        try:
            self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._init_tables()
            self._connected = True
            log.info(f"✅ 資料庫已連線 (SQLite: {DB_PATH})")
        except Exception as e:
            log.error(f"❌ 資料庫連線失敗: {e}")
            raise

    def disconnect(self):
        """安全關閉資料庫。"""
        if self._conn:
            self._conn.close()
            self._connected = False
            log.info("資料庫連線已關閉")

    # ── 表格初始化 ──

    def _init_tables(self):
        """建立必要表格（若不存在）。"""
        cur = self._conn.cursor()

        # 各伺服器設定
        cur.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id    INTEGER PRIMARY KEY,
                config_json TEXT NOT NULL DEFAULT '{}',
                updated_at  REAL NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)

        # 各伺服器狀態（如儀表板訊息 ID、門檻等）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS guild_state (
                guild_id    INTEGER PRIMARY KEY,
                state_json  TEXT NOT NULL DEFAULT '{}',
                updated_at  REAL NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)

        self._conn.commit()

    # ── 通用 CRUD ──

    def get_guild_config(self, guild_id: int) -> dict:
        """取得某伺服器的設定。"""
        cur = self._conn.cursor()
        cur.execute("SELECT config_json FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = cur.fetchone()
        if row:
            return json.loads(row["config_json"])
        return {}

    def set_guild_config(self, guild_id: int, config: dict):
        """寫入某伺服器的設定。"""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO guild_config (guild_id, config_json, updated_at) "
            "VALUES (?, ?, strftime('%s','now')) "
            "ON CONFLICT(guild_id) DO UPDATE SET config_json=?, updated_at=strftime('%s','now')",
            (guild_id, json.dumps(config), json.dumps(config)),
        )
        self._conn.commit()

    def get_guild_state(self, guild_id: int) -> dict:
        """取得某伺服器的執行期狀態。"""
        cur = self._conn.cursor()
        cur.execute("SELECT state_json FROM guild_state WHERE guild_id = ?", (guild_id,))
        row = cur.fetchone()
        if row:
            return json.loads(row["state_json"])
        return {}

    def set_guild_state(self, guild_id: int, state: dict):
        """寫入某伺服器的執行期狀態。"""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO guild_state (guild_id, state_json, updated_at) "
            "VALUES (?, ?, strftime('%s','now')) "
            "ON CONFLICT(guild_id) DO UPDATE SET state_json=?, updated_at=strftime('%s','now')",
            (guild_id, json.dumps(state), json.dumps(state)),
        )
        self._conn.commit()


# ── 單例（整個 Bot 共用一個資料庫連線）──

db: Database = Database()
