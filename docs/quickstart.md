# 🚀 兩分鐘上手 — Edge IoT Discord Bot Framework

## 這是什麼？

一套**通用 Discord Bot 框架** + **邊緣物聯網設備監控系統**。
你可以只取框架來做自己的 Bot，也可以直接使用內建的 RPM 監控應用。

## 快速開始

### 1. 設定環境變數

```bash
cp .env.template .env
# 編輯 .env，填入你的 Discord Token、MQTT Broker 設定
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 啟動系統

有兩種啟動方式：

**方式一：完整系統啟動（Nano + MQTT + Discord）**

```bash
# 先確定 Nano 已接上 USB，且 .env 中 COM_PORT 設定正確
python bridge.py    # 啟動 MQTT ↔ Serial 網關
python bot.py       # 啟動 Discord Bot
```

**方式二：純 Discord Bot 測試（無硬體，建議先用此方式驗證）**

```bash
python bot.py
```

Bot 上線後在 Discord 輸入 `/help` 查看所有可用指令。
使用 `/showcase`（管理員）啟動內建技術導覽。

### 4. 加入你的功能（框架使用）

在 `cogs/` 目錄下新增一個 `.py` 檔案：

```python
# cogs/hello.py
import discord
from discord import app_commands
from discord.ext import commands
from core.bot_base import BotBase

class HelloCog(commands.Cog):
    def __init__(self, bot: BotBase):
        self.bot = bot

    @app_commands.command(name="hello", description="跟 Bot 打招呼")
    async def cmd_hello(self, interaction: discord.Interaction):
        await interaction.response.send_message("哈囉！", ephemeral=True)

async def setup(bot: BotBase):
    await bot.add_cog(HelloCog(bot))
```

> **就是這樣！** 框架會自動掃描 `cogs/` 目錄並載入你的 Cog，**不用修改任何既有檔案**。

---

## 框架提供什麼功能？

| 功能 | 說明 |
|:---|:---|
| ✅ 自動載入 Cog | 在 `cogs/` 新增檔案就自動生效 |
| ✅ 多伺服器支援 | 每個伺服器擁有獨立設定，互不干擾 |
| ✅ SQLite 資料庫 | 狀態自動存檔，不怕 Bot 重啟遺失資料 |
| ✅ 權限系統 | 用裝飾器一鍵檢查權限 |
| ✅ 速率限制 | 防止使用者狂刷指令 |
| ✅ 企業級日誌 | 自動輪替，保留 5 個備份 |
| ✅ 優雅錯誤處理 | 報錯不當機、不洩漏內部資訊 |
| ✅ 內建管理指令 | `/admin-status`, `/admin-reload`, `/help`, `/config` |

---

## 應用案例：Edge IoT RPM Monitor

此框架的第一個應用是**機台轉速監控系統**：

```
Nano (感測器) ──Serial──→ bridge.py ──MQTT──→ HiveMQ Cloud ──MQTT──→ Discord Bot
```

### 核心功能

- **即時儀表板** — 每秒更新 RPM，雜湊比對減少 90% API 請求
- **邊緣觸發警報** — 轉速異常時只發一次 @everyone，持續異常不重複
- **5 秒恢復確認** — 轉速恢復後須維持 5 秒才通知，防門檻跳動
- **三層看門狗** — Bridge 離線（LWT 遺囑）、USB 拔除、感測器當機
- **多伺服器廣播** — 一筆 MQTT 資料同步餵給所有綁定的 Discord

---

## 目錄結構說明

```
├── bot.py              ← 啟動點（極簡，幾乎不動）
├── bridge.py           ← MQTT ↔ Serial 網關（邊緣層）
├── config.py           ← 全局設定
├── .env                ← 環境變數（敏感資訊）
│
├── core/               ← ⭐ 框架核心（複製到新專案時整個帶著）
│   ├── bot_base.py     ← 所有 Bot 繼承的基底
│   ├── db.py           ← 資料庫層
│   ├── guild_state.py  ← 各伺服器狀態管理
│   ├── permissions.py  ← 權限系統
│   ├── ratelimit.py    ← 速率限制
│   ├── errors.py       ← 錯誤處理
│   ├── logging_setup.py← 日誌系統
│   └── utils.py        ← 小工具
│
├── cogs/               ← 🧩 你的功能放這裡
│   ├── builtins/       ← 內建功能（管理、說明、設定）
│   ├── dashboard.py    ← RPM 儀表板
│   ├── alert.py        ← RPM 警報 + 看門狗
│   ├── commands.py     ← RPM 指令
│   └── showcase.py     ← 專題展示
│
├── services/           ← 🔌 外部服務（MQTT）
├── ui/                 ← 🎨 UI 按鈕元件
└── docs/               ← 📄 文件
```

---

## 小提醒

- **要停用某個功能**：把該 `.py` 檔案移到 `cogs/` 外面，或直接刪除
- **要切換資料庫**：改 `.env` 的 `DB_TYPE`（未來支援 PostgreSQL）
- **要調整日誌等級**：改 `.env` 的 `LOG_LEVEL`
- **專題展示**：使用 `/showcase` 指令（需管理員權限）
- **無硬體測試**：可以用 MQTT Client 手動發送 `factory/machine_01/rpm` 主題來模擬轉速資料