"""
Edge IoT RPM Monitor — 🎭 技術導覽展示 Cog
以遙控器方式逐步展示系統五大核心功能。
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, button
from core.bot_base import BotBase


class DemoAlertView(View):
    """展示用警報確認按鈕（不影響真正警報系統）。"""

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="✅ 已確認，靜音 1 分鐘", style=discord.ButtonStyle.success)
    async def ack_btn(self, interaction: discord.Interaction, button: Button):
        button.disabled = True
        button.label = f"✅ {interaction.user.display_name} 已確認"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"⏸️ （展示）警報已靜音，由 {interaction.user.mention} 確認",
            ephemeral=False,
        )


class ShowcaseView(View):
    """手動遙控器 — 逐步引導評審導覽五大核心。"""

    def __init__(self, bot: BotBase, ch: discord.TextChannel):
        super().__init__(timeout=None)
        self.bot = bot
        self.ch = ch
        self.step = 0
        self._sent_messages: list[int] = []  # 追蹤展示產生的訊息 ID，結束時清理

        self.steps = [
            {
                "title": "現實問題 & 系統目標",
                "desc": (
                    "**⼯廠情境**：產線機台可能因軸承磨損、皮帶鬆脫等原因轉速異常，"
                    "若未即時發現，可能導致整批不良品、機台損壞。\n\n"
                    "**傳統作法**：現場人員定時巡檢抄錶，問題回報延遲數小時。\n\n"
                    "**我們的解法**：安裝感測器 + 邊緣運算，將警報直接送到 Discord。\n\n"
                    "**技術架構**：\n"
                    "Nano (感測器) ──Serial──→ bridge.py ──MQTT──→ HiveMQ ──MQTT──→ Discord Bot\n\n"
                    "---\n👉 按下方「下一步講解」繼續"
                ),
                "color": discord.Color.blue(),
            },
            {
                "title": "即時儀表板：RPM 即時監控",
                "desc": (
                    "**實際運作畫面**：以下為此頻道即時生成的儀表板範例（靜態快照）\n\n"
                    "• ⚙️ 即時轉速、🚨 警報門檻、🔔 警報開關狀態\n"
                    "• 🖥️ OLED 面板、🌐 Bridge 連線狀態\n\n"
                    "**工程亮點**：\n"
                    "• 雜湊比對：embed 無變化時不發 API 請求，省 90% 額度\n"
                    "• 429 退避：撞限速時指數後退，不崩潰\n"
                    "• Debounce：1 秒內多次資料更新合併成一次刷新\n\n"
                    "---\n👉 按「下一步」繼續 — 綠色儀表板為正常狀態"
                ),
                "color": discord.Color.green(),
                "action": "spawn_dashboard",
            },
            {
                "title": "智慧警報：邊緣觸發 + 恢復確認",
                "desc": (
                    "轉速低於門檻時，**只發一次** @everyone 警報，不會重複轟炸。\n\n"
                    "**邊緣觸發**：正常→異常觸發一次，持續異常不重複\n"
                    "**5 秒恢復確認**：轉速回到正常後須維持 5 秒才通知恢復，"
                    "防止門檻邊緣跳動造成假通知\n"
                    "**冷卻機制**：警報後須等 60 秒才能再觸發\n\n"
                    "---\n※ 下方將自動發送模擬警報（含確認按鈕）"
                ),
                "color": discord.Color.red(),
                "action": "spawn_alert",
            },
            {
                "title": "看門狗：三層容錯偵測",
                "desc": (
                    "不只監控轉速，還監控系統本身的健康狀態：\n\n"
                    "🔴 **Bridge 離線（LWT 遺囑）**\n"
                    "網關程式崩潰或電腦斷電 → MQTT Broker 自動代發 OFFLINE\n\n"
                    "🔴 **USB 感測器拔除**\n"
                    "Nano 被實體拔除 → 主迴圈捕獲 SerialException → 發送 SENSOR_OFFLINE\n\n"
                    "🔴 **感測器當機**\n"
                    "設備仍在線但停止發送資料 → 看門狗每 10 秒檢查 last_seen 間距\n\n"
                    "任一情況恢復後，自動發送 ✅ 系統恢復通知。"
                ),
                "color": discord.Color.gold(),
            },
            {
                "title": "系統架構 & 工程亮點",
                "desc": (
                    "📦 **模組化框架** — 在 cogs/ 加檔案就自動載入，不需改任何既有程式碼\n\n"
                    "🏢 **多伺服器隔離** — 每台 Discord 有獨立的 GuildState、門檻、開關\n\n"
                    "🛡️ **防禦性設計**\n"
                    "• 429 自動退避 — 撞 API 速率限制時指數退避，不會崩潰\n"
                    "• Bulk Delete — 清空頻道時每批 100 條、間隔 1.5 秒，不觸發 Rate Limit\n"
                    "• 優雅錯誤處理 — 報錯不當機、不洩漏內部資訊\n\n"
                    "🎯 **結論**：從邊緣感測到 Discord 通知，每一層都有工程品質的考量。"
                ),
                "color": discord.Color.purple(),
            },
        ]

    async def _cleanup(self):
        """導覽結束時清理展示產生的訊息。"""
        for msg_id in self._sent_messages:
            try:
                msg = await self.ch.fetch_message(msg_id)
                await msg.delete()
            except (discord.HTTPException, discord.NotFound):
                pass
        self._sent_messages.clear()

    @discord.ui.button(label="👉 下一步講解", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if self.step >= len(self.steps):
            # 導覽結束：清理展示訊息
            await self._cleanup()
            button.disabled = True
            button.label = "✅ 導覽已結束（展示訊息已清理）"
            await interaction.response.edit_message(view=self)
            return

        curr_step = self.steps[self.step]
        self.step += 1

        # ── 1. 先發送說明 embed ──
        embed = discord.Embed(
            title=f"【步驟 {self.step}/5】 {curr_step['title']}",
            description=curr_step["desc"],
            color=curr_step["color"],
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="按遙控器繼續...")
        await interaction.response.send_message(embed=embed, ephemeral=False)

        # ── 2. 再執行示範 action（確保示範出現在說明下方）──
        action = curr_step.get("action")
        if action == "spawn_dashboard":
            # 在當前頻道建立一個「靜態快照」儀表板，不啟動定時更新
            state = self.bot.get_guild_state(interaction.guild_id or 0)
            dash_cog = self.bot.get_cog("DashboardCog")
            if dash_cog and state:
                snapshot_embed = dash_cog.build_embed(interaction.guild_id or 0)
                snapshot_embed.title = "📊 儀表板範例（靜態快照）"
                snapshot_embed.set_footer(text="此為展示用快照，不影響主儀表板更新")
                demo_msg = await self.ch.send(
                    content="── 📊 **即時儀表板範例** ──",
                    embed=snapshot_embed,
                )
                self._sent_messages.append(demo_msg.id)

        elif action == "spawn_alert":
            demo_embed = discord.Embed(
                title="🚨 [技術示範] 偵測到轉速異常低落",
                description=(
                    "這是模擬警報情境，展示邊緣觸發與確認機制。\n\n"
                    "請評審嘗試點擊下方「確認」按鈕：\n"
                    "• 點擊後該按鈕會標記為「xxx 已確認」\n"
                    "• 同時觸發靜音 1 分鐘（對齊冷卻時間）"
                ),
                color=discord.Color.red(),
            )
            alert_msg = await self.ch.send(
                content="⚠️ **示範：邊緣觸發警報推播**",
                embed=demo_embed,
                view=DemoAlertView(),
            )
            self._sent_messages.append(alert_msg.id)


class ConflictOverrideView(View):
    """當使用者在儀表板頻道執行 /showcase 時，顯示警告 + 繼續按鈕。"""

    def __init__(self, bot: BotBase, ch: discord.TextChannel):
        super().__init__(timeout=120)
        self.bot = bot
        self.ch = ch

    @discord.ui.button(label="✅ 繼續導覽", style=discord.ButtonStyle.success)
    async def confirm_btn(self, interaction: discord.Interaction, button: Button):
        # 關閉此確認訊息
        await interaction.response.edit_message(
            content="✅ 已確認，啟動遙控器...", view=None, embed=None
        )
        # 啟動真正的遙控器
        view = ShowcaseView(self.bot, self.ch)
        await interaction.followup.send(
            content="🎭 **遙控器已就緒**（僅您可見）", view=view, ephemeral=True
        )


class ShowcaseCog(commands.Cog):
    def __init__(self, bot: BotBase):
        self.bot = bot

    @app_commands.command(name="showcase", description="🚀 啟動手動遙控式技術導覽")
    async def cmd_showcase(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 僅限管理員", ephemeral=True)
            return

        guild_id = interaction.guild_id or 0
        state = self.bot.get_guild_state(guild_id)

        # 檢查頻道衝突：當前頻道是否為主儀表板頻道
        if state and state.channel_id and state.channel_id == interaction.channel_id:
            hint_embed = discord.Embed(
                title="💡 建議另開頻道",
                description=(
                    "此頻道已設為主要儀表板頻道。在此執行展示會與即時儀表板混雜。\n\n"
                    "**建議**：建立一個 `#技術展示` 頻道，在該頻道執行 `/showcase`。\n\n"
                    "若仍要在本頻道繼續，請點下方「繼續導覽」按鈕。"
                ),
                color=discord.Color.yellow(),
            )
            await interaction.response.send_message(
                content="⚠️ **頻道衝突警告**",
                embed=hint_embed,
                view=ConflictOverrideView(self.bot, interaction.channel),
                ephemeral=True,
            )
        else:
            view = ShowcaseView(self.bot, interaction.channel)
            await interaction.response.send_message(
                content="🎭 **遙控器已就緒**（僅您可見）", view=view, ephemeral=True
            )


async def setup(bot: BotBase):
    await bot.add_cog(ShowcaseCog(bot))