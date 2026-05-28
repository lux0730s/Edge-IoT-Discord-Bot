"""
Edge IoT Discord Bot Framework — Bot 基底
所有 Discord Bot 都應繼承此類別，獲得通用功能。
提供：自動掃描 Cog、資料庫連線、優雅關機、錯誤處理。
"""

import os
import time
import logging
from pathlib import Path

import discord
from discord.ext import commands

from core.db import db
from core.errors import setup_error_handling
from core.guild_state import guild_state_manager

log = logging.getLogger(__name__)


class BotBase(commands.Bot):
    """
    通用 Bot 基底。
    子類別只需覆寫或擴充以下方法：
    - setup_hook(): 加載完 Cogs 後的自訂初始化
    - on_ready(): 上線後的邏輯
    """

    def __init__(self, auto_scan_cogs: bool = True, **kwargs):
        # 設定預設 Intents
        intents = kwargs.pop("intents", discord.Intents.default())
        intents.message_content = True

        super().__init__(
            command_prefix=kwargs.pop("command_prefix", "!"),
            intents=intents,
            **kwargs,
        )

        # 專屬啟動時間
        self.startup_time: float = 0.0
        # 是否自動掃描 cogs/ 目錄
        self._auto_scan = auto_scan_cogs

    # ── 生命週期 ──

    async def setup_hook(self):
        """初始化：資料庫、狀態、Cogs、錯誤處理。"""
        self.startup_time = time.time()

        # 1. 資料庫連線
        db.connect()

        # 2. 自動掃描並載入所有 Cog（包括 builtins 和自訂 Cogs）
        if self._auto_scan:
            await self._scan_and_load_cogs()

        # 3. 註冊全域錯誤處理
        setup_error_handling(self)

        # 4. 同步 Slash Commands
        await self.tree.sync()

        log.info(f"✅ Bot 初始化完成 (啟動耗時: {time.time() - self.startup_time:.2f}s)")

    async def close(self):
        """優雅關機：關閉資料庫連線。"""
        try:
            db.disconnect()
        except Exception as e:
            log.warning(f"資料庫關閉時發生錯誤: {e}")
        await super().close()
        log.info("👋 Bot 已安全關閉")

    # ── Cog 自動掃描 ──

    async def _scan_and_load_cogs(self):
        """
        自動掃描 cogs/ 目錄下的所有 .py 檔案（不含 __init__.py）並載入。
        支援子目錄：cogs/builtins/*.py 也會被載入。
        """
        cogs_dir = Path("cogs")
        if not cogs_dir.exists():
            log.warning("cogs/ 目錄不存在，跳過自動載入")
            return

        loaded = 0
        failed = 0

        # 掃描所有 .py 檔案（遞迴）
        for py_file in cogs_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            # 轉換為模組路徑，例如 cogs/builtins/admin.py → cogs.builtins.admin
            module_path = str(py_file.with_suffix("")).replace(os.sep, ".")

            try:
                await self.load_extension(module_path)
                log.info(f"  ✅ 已載入: {module_path}")
                loaded += 1
            except Exception as e:
                log.error(f"  ❌ 載入失敗 [{module_path}]: {e}")
                failed += 1

        log.info(f"📦 Cog 掃描完成: {loaded} 成功, {failed} 失敗")

    # ── 方便方法 ──

    def get_guild_state(self, guild_id: int = 0):
        """取得指定伺服器的狀態管理器。"""
        return guild_state_manager.get(guild_id)

    def save_guild_state(self, guild_id: int):
        """儲存指定伺服器的狀態。"""
        guild_state_manager.save_all(guild_id)
