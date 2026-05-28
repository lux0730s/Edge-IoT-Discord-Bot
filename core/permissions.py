"""
Edge IoT Discord Bot Framework — 權限系統
提供統一的權限檢查，避免每個 Cog 重複撰寫相同邏輯。
"""

import functools
import discord
from discord import app_commands


class PermissionLevel:
    """權限等級列舉。"""

    EVERYONE = 0    # 所有人
    MODERATOR = 1   # 管理訊息權限
    ADMIN = 2       # 管理伺服器權限
    BOT_OWNER = 3   # Bot 擁有者（開發者）


def check_permission(
    interaction: discord.Interaction,
    level: int = PermissionLevel.EVERYONE,
) -> bool:
    """
    檢查使用者是否有指定權限等級。
    用法：在 slash command 中呼叫此函式，若不通過則回傳 False 並自動回覆使用者。
    """
    # Bot 擁有者（Discord 開發者入口設定的擁有者）
    if level == PermissionLevel.BOT_OWNER:
        app_info = interaction.client.application
        if app_info and interaction.user.id == app_info.owner.id:
            return True
        return False

    # 管理員：擁有 manage_guild 或 administrator
    if level == PermissionLevel.ADMIN:
        if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild:
            return True
        return False

    # 管理員：擁有 manage_messages
    if level == PermissionLevel.MODERATOR:
        if interaction.user.guild_permissions.manage_messages:
            return True
        return False

    # EVERYONE
    return True


def require_permission(level: int = PermissionLevel.MODERATOR):
    """
    裝飾器：自動檢查權限，若不通過則回應錯誤訊息並中止。
    用法：
        @app_commands.command(...)
        @require_permission(PermissionLevel.ADMIN)
        async def my_command(self, interaction: discord.Interaction):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not check_permission(interaction, level):
                level_name = {
                    PermissionLevel.MODERATOR: "管理訊息 (Manage Messages)",
                    PermissionLevel.ADMIN: "管理伺服器 (Administrator)",
                    PermissionLevel.BOT_OWNER: "Bot 擁有者",
                }.get(level, "特定權限")
                await interaction.response.send_message(
                    f"❌ 你沒有執行此指令的權限。需要：**{level_name}**",
                    ephemeral=True,
                )
                return
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator
