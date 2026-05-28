"""
Edge IoT Discord Bot Framework — 內建伺服器設定
讓每個伺服器的管理員可以自訂自己的設定值。
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from core.bot_base import BotBase
from core.permissions import PermissionLevel, require_permission

log = logging.getLogger(__name__)


class GuildConfigCog(commands.Cog):
    """各伺服器自訂設定。"""

    def __init__(self, bot: BotBase):
        self.bot = bot

    @app_commands.command(name="config", description="⚙️ 查看目前伺服器的所有設定")
    async def cmd_config_view(self, interaction: discord.Interaction):
        """查看目前伺服器的設定。"""
        guild_id = interaction.guild_id or 0
        state = self.bot.get_guild_state(guild_id)

        embed = discord.Embed(
            title=f"⚙️ 伺服器設定 - {interaction.guild.name}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="警報門檻", value=f"`{state.threshold} RPM`", inline=True)
        embed.add_field(name="警報開關", value="開啟 🟢" if state.alert_on else "關閉 🔴", inline=True)
        embed.add_field(name="綁定頻道", value=f"<#{state.channel_id}>" if state.channel_id else "未設定", inline=True)
        embed.add_field(name="語言", value=state.language, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="config-set", description="⚙️ 修改伺服器設定（管理員限定）")
    @app_commands.describe(key="要修改的設定名稱", value="新的設定值")
    @require_permission(PermissionLevel.ADMIN)
    async def cmd_config_set(self, interaction: discord.Interaction, key: str, value: str):
        """修改伺服器設定。"""
        guild_id = interaction.guild_id or 0
        state = self.bot.get_guild_state(guild_id)

        allowed_keys = {
            "threshold": int,
            "language": str,
        }

        if key not in allowed_keys:
            allowed = ", ".join(allowed_keys.keys())
            await interaction.response.send_message(
                f"❌ 不支援的設定項。可用設定: {allowed}", ephemeral=True
            )
            return

        try:
            cast = allowed_keys[key]
            parsed = cast(value)
            setattr(state, key, parsed)
            self.bot.save_guild_state(guild_id)
            await interaction.response.send_message(
                f"✅ 已將 `{key}` 設為 `{parsed}`", ephemeral=True
            )
            log.info(f"⚙️ 伺服器 {guild_id} 設定變更: {key}={parsed}（由 {interaction.user}）")
        except (ValueError, TypeError):
            await interaction.response.send_message(
                f"❌ 無法將 `{value}` 轉換為正確的型別", ephemeral=True
            )


async def setup(bot: BotBase):
    await bot.add_cog(GuildConfigCog(bot))
