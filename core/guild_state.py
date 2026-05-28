"""
Edge IoT Discord Bot Framework — 各伺服器獨立狀態管理
每個 Discord 伺服器（Guild）擁有自己獨立的設定與執行期狀態。
"""

import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

from core.db import db

log = logging.getLogger(__name__)


@dataclass
class GuildState:
    """
    單一伺服器的完整狀態。
    包含持久化設定 + 執行期暫存資料。
    """
    # ── 持久化設定 ──
    threshold: int = 100
    alert_on: bool = True
    channel_id: int = 0
    dashboard_msg: int = 0

    # ── 伺服器自訂設定 ──
    custom_prefix: str = ""
    language: str = "zh-TW"

    # ── 執行期暫存（不持久化至 DB 的 config 欄位）──
    rpm: int = -1
    last_seen: float = 0.0
    last_alert: float = 0.0
    bridge_online: bool = False
    sensor_ok: bool = False
    watchdog_notified: bool = False
    oled_ok: bool = True
    last_oled_error: float = 0.0
    dashboard_dismissed: bool = False

    # ── 後設資料 ──
    guild_id: int = 0


class GuildStateManager:
    """
    管理所有伺服器的狀態。
    使用 Database 來持久化，確保不同伺服器的資料完全隔離。
    """

    def __init__(self):
        self._cache: dict[int, GuildState] = {}

    def _config_to_state(self, guild_id: int, config: dict) -> GuildState:
        """從 dict 重建 GuildState。"""
        state = GuildState(guild_id=guild_id)
        for key in ("threshold", "alert_on", "channel_id", "dashboard_msg", "custom_prefix", "language"):
            if key in config:
                setattr(state, key, config[key])
        return state

    def get(self, guild_id: int) -> GuildState:
        """取得指定伺服器的狀態（自動載入快取）。"""
        if guild_id in self._cache:
            return self._cache[guild_id]

        # 從資料庫載入
        config = db.get_guild_config(guild_id)
        state = self._config_to_state(guild_id, config)

        # 也從 guild_state 載入執行期暫存
        runtime = db.get_guild_state(guild_id)
        for key in ("rpm", "last_seen", "last_alert", "bridge_online", "sensor_ok",
                     "watchdog_notified", "oled_ok", "last_oled_error", "dashboard_dismissed"):
            if key in runtime:
                setattr(state, key, runtime[key])

        self._cache[guild_id] = state
        return state

    def save_config(self, guild_id: int):
        """將持久化欄位寫入資料庫。"""
        state = self._cache.get(guild_id)
        if not state:
            return

        config = {
            "threshold": state.threshold,
            "alert_on": state.alert_on,
            "channel_id": state.channel_id,
            "dashboard_msg": state.dashboard_msg,
            "custom_prefix": state.custom_prefix,
            "language": state.language,
        }
        db.set_guild_config(guild_id, config)
        log.debug(f"💾 設定已儲存 (guild={guild_id})")

    def save_runtime(self, guild_id: int):
        """將執行期暫存寫入資料庫。"""
        state = self._cache.get(guild_id)
        if not state:
            return

        runtime = {
            "rpm": state.rpm,
            "last_seen": state.last_seen,
            "last_alert": state.last_alert,
            "bridge_online": state.bridge_online,
            "sensor_ok": state.sensor_ok,
            "watchdog_notified": state.watchdog_notified,
            "oled_ok": state.oled_ok,
            "last_oled_error": state.last_oled_error,
            "dashboard_dismissed": state.dashboard_dismissed,
        }
        db.set_guild_state(guild_id, runtime)

    def save_all(self, guild_id: int):
        """同時儲存設定與執行期狀態。"""
        self.save_config(guild_id)
        self.save_runtime(guild_id)


# ── 全域實例 ──
guild_state_manager: GuildStateManager = GuildStateManager()
