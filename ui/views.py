"""
Edge IoT RPM Monitor — UI 元件模組
集中管理所有 Discord UI Views 與 Buttons。
支援多伺服器：View 操作會經由 Cog 存取對應伺服器的狀態。
"""

import asyncio
import discord
from discord.ui import View, Button

from config import ALERT_COOLDOWN


class StatusView(View):
    """儀表板主要互動介面。"""

    def __init__(self, dashboard_cog):
        super().__init__(timeout=None)
        self.cog = dashboard_cog

    def _get_state(self, interaction: discord.Interaction):
        return self.cog.bot.get_guild_state(interaction.guild_id or 0)

    def _save_state(self, interaction: discord.Interaction):
        self.cog.bot.save_guild_state(interaction.guild_id or 0)

    @discord.ui.button(label="🔔 切換警報", style=discord.ButtonStyle.secondary, custom_id="toggle_alert")
    async def toggle_btn(self, interaction: discord.Interaction, button: Button):
        state = self._get_state(interaction)
        state.alert_on = not state.alert_on
        self._save_state(interaction)
        status = "開啟 🟢" if state.alert_on else "靜音 🔴"
        await interaction.response.send_message(f"警報已切換為 {status}", ephemeral=True)
        await self.cog.update_dashboard(interaction.guild_id or 0)

    @discord.ui.button(label="📍 綁定此頻道", style=discord.ButtonStyle.primary, custom_id="bind_channel")
    async def bind_btn(self, interaction: discord.Interaction, button: Button):
        state = self._get_state(interaction)
        state.channel_id = interaction.channel_id
        state.dashboard_msg = 0
        self._save_state(interaction)
        await interaction.response.send_message("✅ 警報頻道已綁定至此頻道", ephemeral=True)
        await self.cog.spawn_dashboard(interaction.guild_id or 0)

    @discord.ui.button(label="🔄 立即重整", style=discord.ButtonStyle.secondary, custom_id="refresh")
    async def refresh_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await self.cog.update_dashboard(interaction.guild_id or 0)

    @discord.ui.button(label="🗑️ 關閉", style=discord.ButtonStyle.danger, custom_id="close_dashboard")
    async def close_btn(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 需要 Manage Messages 權限", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog.dismiss_dashboard(interaction.guild_id or 0)


class AlertView(View):
    """警報確認介面。"""

    def __init__(self, alert_cog, guild_id: int):
        super().__init__(timeout=ALERT_COOLDOWN)
        self.cog = alert_cog
        self.guild_id = guild_id

    def _get_state(self):
        return self.cog.bot.get_guild_state(self.guild_id)

    def _save_state(self):
        self.cog.bot.save_guild_state(self.guild_id)

    @discord.ui.button(label="✅ 已確認，靜音 1 分鐘", style=discord.ButtonStyle.success)
    async def ack_btn(self, interaction: discord.Interaction, button: Button):
        import time
        state = self._get_state()
        state.last_alert = time.time() + ALERT_COOLDOWN - 10
        self._save_state()
        button.disabled = True
        button.label = f"✅ {interaction.user.display_name} 已確認"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"⏸️ 警報靜音 1 分鐘（由 {interaction.user.mention} 確認）",
            view=UndoView(self.cog, self.guild_id),
        )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        self.stop()


class UndoView(View):
    """取消靜音介面。"""

    def __init__(self, alert_cog, guild_id: int):
        super().__init__(timeout=ALERT_COOLDOWN)
        self.cog = alert_cog
        self.guild_id = guild_id

    def _get_state(self):
        return self.cog.bot.get_guild_state(self.guild_id)

    def _save_state(self):
        self.cog.bot.save_guild_state(self.guild_id)

    @discord.ui.button(label="↩️ 取消靜音，立即恢復警報", style=discord.ButtonStyle.danger)
    async def undo_btn(self, interaction: discord.Interaction, button: Button):
        state = self._get_state()
        state.last_alert = 0
        self._save_state()
        button.disabled = True
        button.label = f"🔔 已恢復（{interaction.user.display_name}）"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔔 警報已恢復，由 {interaction.user.mention} 取消靜音")

    async def on_timeout(self):
        self.stop()


class NukeConfirmView(View):
    """清空頻道確認介面。"""

    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=30)
        self.channel = channel

    @discord.ui.button(label="⚠️ 確認清空所有訊息", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: Button):
        button.disabled = True
        await interaction.response.defer()
        deleted = 0
        # 使用 Bulk Delete（一次最多 100 條），大幅減少 API 請求次數
        while True:
            to_delete = []
            async for msg in self.channel.history(limit=100):
                to_delete.append(msg)
            if not to_delete:
                break
            # 單條訊息無法 bulk delete，回退到單獨刪除
            if len(to_delete) == 1:
                try:
                    await to_delete[0].delete()
                    deleted += 1
                except discord.HTTPException:
                    pass
            else:
                try:
                    await self.channel.delete_messages(to_delete)
                    deleted += len(to_delete)
                except (discord.HTTPException, discord.Forbidden):
                    # 429 或無權限時逐一刪除
                    for msg in to_delete:
                        try:
                            await msg.delete()
                            deleted += 1
                            await asyncio.sleep(0.1)
                        except discord.HTTPException:
                            pass
            await asyncio.sleep(1.5)  # 兩批之間休息，避免撞 bulk delete 的 429
        await interaction.followup.send(f"✅ 已清除 {deleted} 則訊息", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: Button):
        button.disabled = True
        await interaction.response.defer()
        await interaction.followup.send("❌ 已取消清空", ephemeral=True)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class SetupView(View):
    """初始設定綁定介面。"""

    def __init__(self, dashboard_cog):
        super().__init__(timeout=None)
        self.cog = dashboard_cog

    @discord.ui.button(label="📍 將此頻道設為監控頻道", style=discord.ButtonStyle.primary, custom_id="setup_bind")
    async def setup_bind_btn(self, interaction: discord.Interaction, button: Button):
        guild_id = interaction.guild_id or 0
        state = self.cog.bot.get_guild_state(guild_id)
        state.channel_id = interaction.channel_id
        state.dashboard_msg = 0
        self.cog.bot.save_guild_state(guild_id)
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        await interaction.response.send_message("✅ 頻道已綁定，儀表板啟動中…", ephemeral=True)
        await self.cog.spawn_dashboard(guild_id)
        self.stop()
