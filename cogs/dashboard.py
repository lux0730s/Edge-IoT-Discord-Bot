"""
Edge IoT RPM Monitor — 儀表板 Cog
負責儀表板的生成、更新與定時刷新。
支援多伺服器：每個伺服器擁有自己獨立的儀表板。
"""

import asyncio
import time
import logging

import discord
from discord.ext import commands, tasks

from config import DASHBOARD_INTERVAL, WATCHDOG_THRESHOLD
from core.bot_base import BotBase
from core.guild_state import GuildState
from ui.views import StatusView, SetupView

log = logging.getLogger(__name__)


class DashboardCog(commands.Cog):
    def __init__(self, bot: BotBase):
        self.bot = bot
        self._dashboard_lock = asyncio.Lock()
        self._debounce_tasks: dict[int, asyncio.Task] = {}  # guild_id → 延遲更新任務
        self._last_snapshot: dict[int, str] = {}  # guild_id → embed 內容雜湊
        self._ratelimit_until: dict[int, float] = {}  # guild_id → 429 解封時間戳

    async def cog_load(self):
        # 註冊 persistent views（多伺服器，每個 view 綁定自己的 cog）
        self.bot.add_view(StatusView(self))
        self.bot.add_view(SetupView(self))
        self._dashboard_loop.start()

    async def cog_unload(self):
        self._dashboard_loop.cancel()

    # ── 輔助：取得伺服器狀態 ──

    def _get_state(self, guild_id: int) -> GuildState:
        return self.bot.get_guild_state(guild_id)

    def _save_state(self, guild_id: int):
        self.bot.save_guild_state(guild_id)

    # ── 儀表板管理 ──

    def _embed_hash(self, guild_id: int) -> str:
        """產生 embed 內容的簡短雜湊，用於比對有無變化。"""
        s = self._get_state(guild_id)
        gap = time.time() - s.last_seen if s.last_seen else -1
        return f"{s.rpm}|{s.bridge_online}|{s.sensor_ok}|{s.oled_ok}|{s.alert_on}|{s.threshold}|{gap:.1f}"

    def _is_ratelimited(self, guild_id: int) -> bool:
        """檢查此伺服器是否在 429 退避中。"""
        until = self._ratelimit_until.get(guild_id, 0)
        if time.time() < until:
            return True
        return False

    def build_embed(self, guild_id: int) -> discord.Embed:
        """建構儀表板 Embed（使用指定伺服器的狀態）。"""
        s = self._get_state(guild_id)
        gap = time.time() - s.last_seen if s.last_seen else -1

        if gap < 0:
            rpm_text = "等待資料..."
        elif not s.bridge_online:
            rpm_text = f"❌ 網關離線 (最後: {s.rpm})"
        elif not s.sensor_ok:
            rpm_text = f"🔌 USB 已拔除 (最後: {s.rpm})"
        elif gap > WATCHDOG_THRESHOLD:
            rpm_text = f"⚠️ 感測器中斷 {gap:.0f}s (最後: {s.rpm})"
        else:
            rpm_text = f"{s.rpm} RPM"

        if not s.bridge_online or not s.sensor_ok or gap > WATCHDOG_THRESHOLD:
            color = discord.Color.dark_gray()
        elif not s.alert_on:
            color = discord.Color.greyple()
        elif s.rpm == 0:
            color = discord.Color.red()
        elif s.rpm < s.threshold:
            color = discord.Color.orange()
        else:
            color = discord.Color.green()

        embed = discord.Embed(
            title="📊 機台監控儀表板 (MQTT)",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="⚙️ 即時轉速", value=f"```{rpm_text}```", inline=False)
        embed.add_field(name="🚨 警報門檻", value=f"`{s.threshold} RPM`", inline=True)
        embed.add_field(name="🔔 警報狀態", value="開啟 🟢" if s.alert_on else "靜音 🔴", inline=True)
        embed.add_field(name="🖥️ OLED", value="正常 ✅" if s.oled_ok else "故障 ⚠️", inline=True)
        embed.add_field(name="🌐 網關(Bridge)", value="連線 ✅" if s.bridge_online else "離線 ❌", inline=True)
        embed.set_footer(text="Edge IoT Monitor • MQTT Cloud")
        return embed

    async def spawn_dashboard(self, guild_id: int | None = None):
        """建立新的儀表板訊息。"""
        async with self._dashboard_lock:
            # 若未指定 guild_id，使用狀態中第一個
            if guild_id is None:
                for g in self.bot.guilds:
                    s = self._get_state(g.id)
                    if s.channel_id:
                        guild_id = g.id
                        break
                if guild_id is None:
                    return

            ch = await self._get_channel(guild_id)
            if not ch:
                return

            s = self._get_state(guild_id)
            if s.dashboard_msg:
                try:
                    old_msg = await ch.fetch_message(s.dashboard_msg)
                    await old_msg.delete()
                except discord.HTTPException:
                    pass

            embed = self.build_embed(guild_id)
            msg = await ch.send(embed=embed, view=StatusView(self))
            s.dashboard_msg = msg.id
            s.dashboard_dismissed = False
            self._last_snapshot[guild_id] = self._embed_hash(guild_id)
            self._save_state(guild_id)

    async def dismiss_dashboard(self, guild_id: int | None = None):
        """關閉儀表板。"""
        async with self._dashboard_lock:
            if guild_id is None:
                return

            s = self._get_state(guild_id)
            if not s.dashboard_msg:
                return

            ch = await self._get_channel(guild_id)
            if ch:
                try:
                    msg = await ch.fetch_message(s.dashboard_msg)
                    await msg.delete()
                except discord.HTTPException:
                    pass

            s.dashboard_msg = 0
            s.dashboard_dismissed = True
            self._save_state(guild_id)

        # 清除該伺服器的 debounce/ratelimit 狀態
        self._debounce_tasks.pop(guild_id, None)
        self._ratelimit_until.pop(guild_id, None)
        self._last_snapshot.pop(guild_id, None)

    def _schedule_update(self, guild_id: int):
        """延遲合併儀表板更新請求（debounce 0.5 秒）。"""
        # 取消前一個待處理的更新
        existing = self._debounce_tasks.get(guild_id)
        if existing and not existing.done():
            existing.cancel()

        # 建立新的延遲任務
        async def _delayed_update():
            try:
                await asyncio.sleep(0.5)
                await self._do_update(guild_id)
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception(f"儀表板更新異常 guild={guild_id}")

        self._debounce_tasks[guild_id] = asyncio.create_task(_delayed_update())

    async def _do_update(self, guild_id: int):
        """實際執行儀表板編輯（含雜湊比對與 429 退避）。"""
        async with self._dashboard_lock:
            if guild_id is None:
                return

            # 429 退避檢查
            if self._is_ratelimited(guild_id):
                return

            s = self._get_state(guild_id)
            if not s.dashboard_msg:
                return

            # 比對 embed 內容是否有變化，沒變就不發 API
            current_hash = self._embed_hash(guild_id)
            if self._last_snapshot.get(guild_id) == current_hash:
                return
            self._last_snapshot[guild_id] = current_hash

            ch = await self._get_channel(guild_id)
            if not ch:
                return

            try:
                msg = await ch.fetch_message(s.dashboard_msg)
                await msg.edit(embed=self.build_embed(guild_id), view=StatusView(self))
            except discord.NotFound:
                s.dashboard_msg = 0
                self._save_state(guild_id)
            except discord.HTTPException as e:
                # 撞 429 → 自動退避 30 秒
                if e.status == 429:
                    retry_after = 30
                    self._ratelimit_until[guild_id] = time.time() + retry_after
                    log.warning(f"⚠️ 429 速率限制 guild={guild_id}，退避 {retry_after}s")

    async def update_dashboard(self, guild_id: int | None = None):
        """更新現有儀表板內容（透過 debounce 合併請求）。"""
        if guild_id is None:
            return
        self._schedule_update(guild_id)

    @tasks.loop(seconds=DASHBOARD_INTERVAL)
    async def _dashboard_loop(self):
        """定時更新所有伺服器的儀表板（僅執行 spawn，edit 交給 debounce）。"""
        for guild in self.bot.guilds:
            s = self._get_state(guild.id)
            if not s.channel_id:
                continue
            if not s.dashboard_msg and not s.dashboard_dismissed:
                await self.spawn_dashboard(guild.id)
            elif s.dashboard_msg:
                self._schedule_update(guild.id)

    @_dashboard_loop.before_loop
    async def _before_dashboard_loop(self):
        await self.bot.wait_until_ready()

    # ── 工具方法 ──

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


async def setup(bot: BotBase):
    """Cog 載入入口（由 bot.load_extension 呼叫）。"""
    await bot.add_cog(DashboardCog(bot))
