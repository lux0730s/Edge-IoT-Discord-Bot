"""
Edge IoT RPM Monitor — 警報 Cog
負責警報觸發邏輯與看門狗監控。
支援多伺服器：每個伺服器有自己獨立的警報狀態。
"""

import time
import logging

import discord
from discord.ext import commands, tasks

from config import ALERT_COOLDOWN, WATCHDOG_THRESHOLD, STARTUP_GRACE
from core.bot_base import BotBase
from core.guild_state import GuildState
from ui.views import AlertView

log = logging.getLogger(__name__)


class AlertCog(commands.Cog):
    def __init__(self, bot: BotBase):
        self.bot = bot
        self._startup_time = bot.startup_time
        self._prev_alert_state: dict[int, bool] = {}  # guild_id → 前一次是否為異常狀態
        self._recovery_pending_start: dict[int, float] = {}  # guild_id → 恢復計時開始時間

    async def cog_load(self):
        self._watchdog_loop.start()

    async def cog_unload(self):
        self._watchdog_loop.cancel()

    # ── 輔助 ──

    def _get_state(self, guild_id: int) -> GuildState:
        return self.bot.get_guild_state(guild_id)

    def _save_state(self, guild_id: int):
        self.bot.save_guild_state(guild_id)

    async def _get_channel(self, guild_id: int):
        s = self._get_state(guild_id)
        cid = s.channel_id
        if not cid:
            return None
        ch = self.bot.get_channel(cid)
        if ch is None:
            try:
                ch = await self.bot.fetch_channel(cid)
            except discord.HTTPException:
                return None
        return ch

    # ── 警報檢查（邊緣觸發 + 5 秒恢復確認）──

    RECOVERY_DEBOUNCE = 5  # 恢復確認秒數：轉速須連續維持正常 N 秒才發恢復通知

    async def check_alert(self, guild_id: int, rpm: int):
        """
        邊緣觸發警報，恢復須維持 5 秒穩定：
        - 正常 → 異常：發送🚨異常警報（受冷卻限制）
        - 異常並持續正常 5 秒：發送✅恢復通知
        - 持續異常 / 持續正常：不做事
        - 異常後正常但未滿 5 秒又異常：不發恢復通知（防門檻跳動）
        """
        s = self._get_state(guild_id)
        startup_grace = time.time() - self._startup_time < STARTUP_GRACE
        if startup_grace or not s.alert_on:
            return

        now_abnormal = rpm < s.threshold
        prev_abnormal = self._prev_alert_state.get(guild_id, False)
        self._prev_alert_state[guild_id] = now_abnormal

        if now_abnormal:
            # 目前異常中 → 取消任何待處理的恢復計時
            self._recovery_pending_start.pop(guild_id, None)

        ch = await self._get_channel(guild_id)
        if not ch:
            return

        if now_abnormal and not prev_abnormal:
            # 🟢 正常 → 🔴 異常：第一次異常，受冷卻限制
            if time.time() - s.last_alert < ALERT_COOLDOWN:
                return

            embed = discord.Embed(
                title="🚨 機台異常警報",
                color=discord.Color.red() if rpm == 0 else discord.Color.orange(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="目前轉速", value=f"`{rpm} RPM`", inline=True)
            embed.add_field(name="警報門檻", value=f"`{s.threshold} RPM`", inline=True)
            await ch.send(content="@everyone", embed=embed, view=AlertView(self, guild_id))
            s.last_alert = time.time()
            self._save_state(guild_id)

        elif not now_abnormal:
            if prev_abnormal:
                # 🔴 異常 → 🟢 正常（第一次）：啟動 5 秒恢復計時，還不通知
                self._recovery_pending_start[guild_id] = time.time()
            else:
                # 持續正常中：檢查 5 秒確認是否完成
                pending_start = self._recovery_pending_start.get(guild_id)
                if pending_start is not None and time.time() - pending_start >= self.RECOVERY_DEBOUNCE:
                    self._recovery_pending_start.pop(guild_id, None)
                    embed = discord.Embed(
                        title="✅ 機台已恢復正常",
                        description=(
                            f"轉速 `{rpm} RPM` 已穩定維持超過 {self.RECOVERY_DEBOUNCE} 秒，"
                            f"回到門檻 `{s.threshold} RPM` 以上"
                        ),
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow(),
                    )
                    await ch.send(embed=embed)

    # ── 看門狗 ──

    @tasks.loop(seconds=10)
    async def _watchdog_loop(self):
        """看門狗：偵測所有伺服器的系統離線狀態。"""
        for guild in self.bot.guilds:
            await self._check_watchdog(guild.id)

    async def _check_watchdog(self, guild_id: int):
        s = self._get_state(guild_id)
        if not s.last_seen:
            return

        gap = time.time() - s.last_seen
        is_offline = (not s.bridge_online) or (not s.sensor_ok) or (gap > WATCHDOG_THRESHOLD)
        startup_grace = time.time() - self._startup_time < STARTUP_GRACE

        if is_offline and s.alert_on and not s.watchdog_notified and not startup_grace:
            ch = await self._get_channel(guild_id)
            if ch:
                reason = (
                    "電腦斷網或關機 (Bridge 離線)" if not s.bridge_online
                    else "USB 感測器被實體拔除" if not s.sensor_ok
                    else f"感測器當機，已 {gap:.0f} 秒未發送資料"
                )
                await ch.send(embed=discord.Embed(
                    title="⚠️ 系統離線警報",
                    description=f"原因：**{reason}**\n請檢查現場設備狀態。",
                    color=discord.Color.dark_gray(),
                    timestamp=discord.utils.utcnow(),
                ))
            s.watchdog_notified = True
            self._save_state(guild_id)

        elif not is_offline and gap < 10 and s.watchdog_notified:
            s.watchdog_notified = False
            self._save_state(guild_id)
            ch = await self._get_channel(guild_id)
            if ch:
                await ch.send(embed=discord.Embed(
                    title="✅ 系統已恢復",
                    description="資料流已重新接收，監控恢復正常",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow(),
                ))

    @_watchdog_loop.before_loop
    async def _before_watchdog(self):
        await self.bot.wait_until_ready()


async def setup(bot: BotBase):
    await bot.add_cog(AlertCog(bot))
