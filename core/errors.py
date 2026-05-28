"""
Edge IoT Discord Bot Framework — 錯誤處理
統一的錯誤處理，確保 Bot 不會因非預期錯誤而當機，
且不向使用者洩露內部實作細節。
"""

import traceback
import logging

import discord
from discord import app_commands

log = logging.getLogger(__name__)


class AppError(Exception):
    """應用層級的可預期錯誤（會友善提示使用者，不記錄堆疊）。"""
    def __init__(self, message: str, ephemeral: bool = True):
        self.message = message
        self.ephemeral = ephemeral
        super().__init__(message)


async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    """
    全域錯誤處理器（註冊在 bot.tree.on_error）。
    所有的 Slash Command 錯誤都會經過這裡。
    """
    # 檢查類型的錯誤（由 require_permission 觸發）
    if isinstance(error, app_commands.CheckFailure):
        # 已由 require_permission 自行處理回覆，這裡忽略
        return

    # 可預期的應用錯誤
    if isinstance(error.__cause__, AppError):
        app_err = error.__cause__
        await _safe_reply(interaction, f"❌ {app_err.message}", app_err.ephemeral)
        return

    # 非預期錯誤（記錄完整堆疊但不洩露給使用者）
    log.error(f"❗ 未預期的指令錯誤: {interaction.command}\n{traceback.format_exc()}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send("❌ 執行指令時發生非預期錯誤，請稍後再試", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 執行指令時發生非預期錯誤，請稍後再試", ephemeral=True)
    except Exception:
        pass


async def _safe_reply(interaction: discord.Interaction, content: str, ephemeral: bool = True):
    """安全回覆，避免因 interaction 已回應而報錯。"""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception as e:
        log.warning(f"無法回覆錯誤訊息: {e}")


def setup_error_handling(bot):
    """將全域錯誤處理器註冊到 Bot。"""
    bot.tree.on_error = on_app_command_error
    log.info("✅ 全域錯誤處理器已註冊")
