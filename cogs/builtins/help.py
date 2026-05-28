"""
Edge IoT Discord Bot Framework — 內建說明系統
自動掃描所有已註冊的 Slash Command 並產生說明選單。
"""

import discord
from discord import app_commands
from discord.ext import commands

from core.bot_base import BotBase


class HelpCog(commands.Cog):
    """自動產生的指令說明系統。"""

    def __init__(self, bot: BotBase):
        self.bot = bot

    @app_commands.command(name="help", description="📖 查看所有可用的指令與說明")
    async def cmd_help(self, interaction: discord.Interaction):
        """顯示所有已註冊的 Slash Command。"""
        commands = self.bot.tree.get_commands()

        if not commands:
            await interaction.response.send_message("目前沒有任何可用指令。", ephemeral=True)
            return

        embed = discord.Embed(
            title="📖 指令說明",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        for cmd in commands:
            # 跳過只在特定 guild 註冊的指令
            description = cmd.description or "無說明"
            embed.add_field(
                name=f"/{cmd.name}",
                value=description,
                inline=False,
            )

        embed.set_footer(text=f"共 {len(commands)} 個指令 • Edge IoT Framework")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: BotBase):
    await bot.add_cog(HelpCog(bot))
