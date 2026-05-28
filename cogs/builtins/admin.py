"""
Edge IoT Discord Bot Framework — 內建管理指令
提供 Bot 擁有者與伺服器管理員的系統指令。
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from core.bot_base import BotBase
from core.permissions import PermissionLevel, require_permission
from core.utils import format_uptime

log = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    """管理員專用指令。"""

    def __init__(self, bot: BotBase):
        self.bot = bot

    @app_commands.command(name="admin-status", description="📊 查看 Bot 執行狀態與系統資訊")
    @require_permission(PermissionLevel.MODERATOR)
    async def cmd_status(self, interaction: discord.Interaction):
        """顯示 Bot 的執行狀態。"""
        guild = interaction.guild
        uptime_str = format_uptime(self.bot.startup_time)

        embed = discord.Embed(
            title="🤖 Bot 系統狀態",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="上線時間", value=uptime_str, inline=True)
        embed.add_field(name="延遲", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="所在伺服器", value=guild.name if guild else "N/A", inline=True)

        if guild:
            embed.add_field(name="已載入模組", value=f"{len(self.bot.cogs)} 個", inline=True)
            embed.add_field(name="Slash 指令", value=f"{len(self.bot.tree.get_commands())} 個", inline=True)

        embed.set_footer(text="Edge IoT Discord Bot Framework")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="admin-reload", description="🔄 重新載入指定的 Cog 模組")
    @app_commands.describe(module="模組名稱（例如: cogs.dashboard）")
    @require_permission(PermissionLevel.ADMIN)
    async def cmd_reload(self, interaction: discord.Interaction, module: str):
        """重新載入指定的 Cog。"""
        try:
            self.bot.unload_extension(module)
            await self.bot.load_extension(module)
            await interaction.response.send_message(
                f"✅ 模組 `{module}` 已重新載入", ephemeral=True
            )
            log.info(f"🔄 管理員 {interaction.user} 重新載入了 {module}")
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 重新載入失敗: {e}", ephemeral=True
            )

    @app_commands.command(name="admin-list", description="📋 列出所有已載入的模組")
    @require_permission(PermissionLevel.MODERATOR)
    async def cmd_list(self, interaction: discord.Interaction):
        """列出所有已載入的 Cog。"""
        cog_list = "\n".join(f"- `{name}`" for name in sorted(self.bot.cogs.keys()))
        await interaction.response.send_message(
            f"📋 **已載入模組 ({len(self.bot.cogs)} 個)**\n{cog_list}",
            ephemeral=True,
        )


async def setup(bot: BotBase):
    await bot.add_cog(AdminCog(bot))
