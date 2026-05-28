"""
Edge IoT RPM Monitor — 指令 Cog
集中管理所有 Slash Commands。
支援多伺服器：指令會操作當前伺服器的獨立設定。
"""

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from core.bot_base import BotBase
from core.guild_state import GuildState
from core.permissions import PermissionLevel, require_permission
from core.utils import validate_rpm
from ui.views import NukeConfirmView

log = logging.getLogger(__name__)


class CommandsCog(commands.Cog):
    def __init__(self, bot: BotBase):
        self.bot = bot

    def _get_state(self, interaction: discord.Interaction) -> GuildState:
        return self.bot.get_guild_state(interaction.guild_id or 0)

    def _save_state(self, interaction: discord.Interaction):
        self.bot.save_guild_state(interaction.guild_id or 0)

    # ── /status ──

    @app_commands.command(name="status", description="在目前頻道召喚即時儀表板")
    async def cmd_status(self, interaction: discord.Interaction):
        s = self._get_state(interaction)
        s.channel_id = interaction.channel_id
        s.dashboard_msg = 0
        self._save_state(interaction)
        await interaction.response.send_message("📊 儀表板已召喚", ephemeral=True)

        dashboard_cog = self.bot.get_cog("DashboardCog")
        if dashboard_cog:
            await dashboard_cog.spawn_dashboard(interaction.guild_id or 0)

    # ── /threshold ──

    @app_commands.command(name="threshold", description="設定警報轉速門檻")
    @app_commands.describe(rpm="低於此值觸發警報（1–99999）")
    async def cmd_threshold(self, interaction: discord.Interaction, rpm: int):
        err = validate_rpm(rpm)
        if err:
            await interaction.response.send_message(f"❌ {err}", ephemeral=True)
            return
        if rpm == 0:
            await interaction.response.send_message("❌ 門檻不能為 0", ephemeral=True)
            return

        s = self._get_state(interaction)
        s.threshold = rpm
        self._save_state(interaction)

        # 透過 MQTT 服務發布門檻
        if hasattr(self.bot, "mqtt_service") and self.bot.mqtt_service:
            self.bot.mqtt_service.publish_threshold(rpm)

        await interaction.response.send_message(
            f"✅ 門檻設為 `{rpm} RPM`，已透過 MQTT 發送", ephemeral=True
        )

        dashboard_cog = self.bot.get_cog("DashboardCog")
        if dashboard_cog:
            await dashboard_cog.update_dashboard(interaction.guild_id or 0)

    # ── /info ──

    @app_commands.command(name="info", description="查看目前所有設定與連線狀態")
    async def cmd_info(self, interaction: discord.Interaction):
        s = self._get_state(interaction)
        embed = discord.Embed(title="ℹ️ 系統資訊", color=discord.Color.blurple())
        embed.add_field(name="網關狀態", value="線上 🟢" if s.bridge_online else "離線 🔴")
        embed.add_field(name="感測器", value="連線 ✅" if s.sensor_ok else "斷開 ❌")
        embed.add_field(
            name="警報狀態",
            value=f"{'開啟 🟢' if s.alert_on else '靜音 🔴'} (<{s.threshold} RPM)",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /cleanup ──

    @app_commands.command(name="cleanup", description="清除頻道中殘留的舊儀表板訊息")
    @app_commands.describe(count="要掃描的訊息數量（最多 200）")
    async def cmd_cleanup(self, interaction: discord.Interaction, count: int = 50):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 無權限", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        deleted = 0
        s = self._get_state(interaction)
        async for msg in interaction.channel.history(limit=min(max(count, 1), 200)):
            if (
                msg.author == self.bot.user
                and msg.embeds
                and "儀表板" in (msg.embeds[0].title or "")
                and msg.id != s.dashboard_msg
            ):
                try:
                    await msg.delete()
                    deleted += 1
                    await asyncio.sleep(0.5)
                except discord.HTTPException:
                    pass
        await interaction.followup.send(f"🧹 已清除 {deleted} 則舊儀表板訊息", ephemeral=True)

    # ── /nuke ──

    @app_commands.command(name="nuke", description="⚠️ 清空此頻道所有訊息（僅限管理員）")
    @require_permission(PermissionLevel.MODERATOR)
    async def cmd_nuke(self, interaction: discord.Interaction):
        view = NukeConfirmView(interaction.channel)
        embed = discord.Embed(
            title="⚠️ 危險操作",
            description=(
                f"確定要清空 **{interaction.channel.mention}** 的所有訊息嗎？\n"
                "此操作**不可逆**"
            ),
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: BotBase):
    await bot.add_cog(CommandsCog(bot))
