"""
Edge IoT RPM Monitor — 主入口
職責：初始化 Bot、載入 Cogs（自動掃描）、啟動 MQTT 服務。
使用 BotBase 框架，獲得自動 Cog 掃描、資料庫、錯誤處理等能力。
"""

import time
import logging

import discord

from config import DISCORD_TOKEN, TOPIC_RPM, TOPIC_STATUS, OLED_RESET_TIMEOUT
from core.bot_base import BotBase
from core.guild_state import GuildState
from core.logging_setup import setup_logging
from services.mqtt_service import MqttService

log = logging.getLogger(__name__)


class MonitorBot(BotBase):
    """
    RPM 監控 Bot。
    繼承 BotBase 以獲得：
    - 自動掃描 cogs/ 目錄載入所有模組
    - 資料庫連線與伺服器隔離
    - 全域錯誤處理
    - 優雅關機
    """

    def __init__(self):
        super().__init__(auto_scan_cogs=True)
        self.mqtt_service: MqttService | None = None

    async def setup_hook(self):
        # 先讓 BotBase 初始化資料庫、載入 Cogs、註冊錯誤處理
        await super().setup_hook()

        # 啟動 MQTT 服務
        self.mqtt_service = MqttService(
            on_message=self._handle_mqtt_message,
            loop=self.loop,
        )
        self.mqtt_service.start()

    async def on_ready(self):
        # 更新狀態顯示：正在玩「管理 N 台伺服器」
        guild_count = len(self.guilds)
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name=f"管理 {guild_count} 台伺服器",
        )
        await self.change_presence(activity=activity)

        log.info(f"Bot 上線: {self.user}（服務 {guild_count} 台伺服器）")

        # 對每個 Bot 有權限的伺服器，檢查是否需要重啟儀表板
        for guild in self.guilds:
            state = self.get_guild_state(guild.id)
            if state.channel_id:
                dashboard_cog = self.get_cog("DashboardCog")
                if dashboard_cog:
                    await dashboard_cog.spawn_dashboard(guild_id=guild.id)

    async def on_message_delete(self, message: discord.Message):
        """監聽訊息刪除事件，更新儀表板狀態。"""
        if not message.guild:
            return
        state = self.get_guild_state(message.guild.id)
        if message.id == state.dashboard_msg:
            state.dashboard_msg = 0
            state.dashboard_dismissed = True
            self.save_guild_state(message.guild.id)

    async def close(self):
        if self.mqtt_service:
            self.mqtt_service.stop()
        await super().close()

    # ── MQTT 訊息處理（轉發至對應 Cog）──

    async def _handle_mqtt_message(self, topic: str, payload: str):
        """
        處理 MQTT 訊息。
        將 RPM/狀態廣播至所有已綁定頻道的伺服器：
        - 每個 guild 的 GuildState 各自獨立更新
        - 每個 guild 的 AlertCog 各自獨立判斷門檻與冷卻
        """
        # 篩選出已綁定頻道的 guild
        target_guilds = []
        for guild in self.guilds:
            state = self.get_guild_state(guild.id)
            if state.channel_id:
                target_guilds.append(guild.id)

        if not target_guilds:
            return

        if topic == TOPIC_STATUS:
            for guild_id in target_guilds:
                state = self.get_guild_state(guild_id)
                self._handle_status_payload(state, payload)
                self.save_guild_state(guild_id)

        elif topic == TOPIC_RPM:
            try:
                rpm = int(payload)
            except ValueError:
                return

            alert_cog = self.get_cog("AlertCog")

            for guild_id in target_guilds:
                state = self.get_guild_state(guild_id)
                state.bridge_online = True
                state.sensor_ok = True
                state.last_seen = time.time()
                state.rpm = rpm

                if not state.oled_ok and (time.time() - state.last_oled_error > OLED_RESET_TIMEOUT):
                    state.oled_ok = True

                self.save_guild_state(guild_id)

                # 委派給 AlertCog 檢查警報（每個 guild 各自獨立判斷）
                if alert_cog:
                    await alert_cog.check_alert(guild_id, rpm)

    def _resolve_guild_id(self) -> int | None:
        """
        解析 MQTT 訊息要對應到哪個伺服器。
        目前取第一個有 channel_id 的伺服器。
        未來可依 MQTT topic 路由到不同 guild。
        """
        for guild in self.guilds:
            state = self.get_guild_state(guild.id)
            if state.channel_id:
                return guild.id
        # 若找不到已綁定的，回傳第一個伺服器
        if self.guilds:
            return self.guilds[0].id
        return None

    def _handle_status_payload(self, s: GuildState, payload: str):
        """解析狀態主題的各種 payload。"""
        if payload == "ONLINE":
            if not s.bridge_online:
                log.info("🌐 Bridge 網關已上線")
            s.bridge_online = True
        elif payload == "OFFLINE":
            s.bridge_online = False
            log.warning("⚠️ Bridge 網關異常離線 (遺囑 LWT)")
        elif payload == "OLED_ERROR":
            s.oled_ok = False
            s.last_oled_error = time.time()
            log.warning("收到 Nano OLED_ERROR")
        elif payload == "SENSOR_ONLINE":
            s.sensor_ok = True
            log.info("🔌 現場 USB 感測器已連線")
        elif payload == "SENSOR_OFFLINE":
            s.sensor_ok = False
            log.warning("⚠️ 現場 USB 感測器已拔除")


if __name__ == "__main__":
    setup_logging(level="INFO")
    bot = MonitorBot()
    bot.run(DISCORD_TOKEN)

