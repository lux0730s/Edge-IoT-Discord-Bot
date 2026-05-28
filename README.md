# Edge IoT Discord Bot Framework

一套**通用 Discord Bot 框架**，支援多伺服器、企業級日誌、權限分級、速率限制。
目前第一個應用案例是 **Edge IoT RPM Monitor**（機台轉速監控系統）。

## ✨ 框架特色

| 功能 | 說明 |
|:---|:---|
| 🔌 **自動載入 Cog** | 在 `cogs/` 新增檔案就自動生效，**不用修改任何既有程式碼** |
| 🌍 **多伺服器支援** | 每個伺服器擁有獨立設定，資料完全隔離 |
| 🗄️ **資料庫儲存** | SQLite 內建，未來可無痛切換 PostgreSQL |
| 🛡️ **權限分級** | 所有人 → 管理員 → 伺服器管理 → Bot 擁有者 |
| ⏱️ **速率限制** | 防止濫用，保護 Bot 不被刷爆 |
| 📋 **企業級日誌** | 自動輪替檔案日誌，保留 5 個備份 |
| 🚨 **優雅錯誤處理** | 報錯不當機、不洩漏內部資訊 |
| 🎛️ **內建管理指令** | `/admin-status`, `/admin-reload`, `/help`, `/config` |

## 🏗️ 整體架構

```
                         ┌──────────────────┐
                         │  Arduino Nano     │ 邊緣層
                         │  (USB Serial)     │
                         └────────┬─────────┘
                                  │ Serial USB
                         ┌────────▼─────────┐
                         │  bridge.py        │ 網關層
                         │  (MQTT ↔ Serial)  │
                         └────────┬─────────┘
                                  │ MQTT Publish
                         ┌────────▼─────────┐
                         │  MQTT Broker      │ 雲端層
                         │  (HiveMQ Cloud)   │
                         └────────┬─────────┘
                                  │ MQTT Subscribe
                         ┌────────▼─────────┐
                         │  bot.py           │ Discord Bot
                         │  (MonitorBot)     │
                         └────────┬─────────┘
                                  │ 廣播至所有已綁定伺服器
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              Discord A      Discord B      Discord C
            (獨立 GuildState) (獨立 GuildState) (獨立 GuildState)
```

### 目錄結構

```
├── bot.py              ← 啟動點（極簡，幾乎不動）
├── bridge.py           ← MQTT ↔ Serial 網關（邊緣層）
├── config.py           ← 全局設定
├── .env                ← 環境變數（敏感資訊）
│
├── core/               ← ⭐ 框架核心（複製到新專案時整個帶著）
│   ├── bot_base.py     ← Bot 基底（所有 Bot 繼承此類別）
│   ├── db.py           ← 資料庫抽象層（SQLite）
│   ├── guild_state.py  ← 各伺服器獨立狀態管理
│   ├── permissions.py  ← 權限系統（裝飾器一鍵檢查）
│   ├── ratelimit.py    ← 速率限制
│   ├── errors.py       ← 全域錯誤處理
│   ├── logging_setup.py← 企業級日誌（自動輪替）
│   └── utils.py        ← 常用小工具
│
├── cogs/               ← 🧩 你的功能放這裡
│   ├── builtins/       ← 內建功能（每個 Bot 都有）
│   │   ├── admin.py    ← 管理指令
│   │   ├── help.py     ← 說明系統
│   │   └── guild_config.py ← 伺服器設定
│   │
│   ├── dashboard.py    ← RPM 儀表板（即時更新 + debounce + 雜湊比對）
│   ├── alert.py        ← RPM 警報（邊緣觸發 + 5 秒恢復確認 + 看門狗）
│   ├── commands.py     ← RPM 指令
│   └── showcase.py     ← 專題展示（可移除）
│
├── services/           ← 🔌 外部服務
│   └── mqtt_service.py ← MQTT 連線
│
├── ui/                 ← 🎨 UI 元件
│   └── views.py        ← 按鈕、選單
│
└── docs/               ← 📄 開發文件
    └── quickstart.md   ← 兩分鐘上手
```

## ⚙️ 應用案例：Edge IoT RPM Monitor

### 系統流程

```
Nano (感測器) ──Serial──→ bridge.py ──MQTT──→ HiveMQ Cloud ──MQTT──→ bot.py ──→ Discord
    ▲                                                                         │
    │                                                     ┌───────────────────┤
    └─────────────── 雲端指令 (門檻設定) ────────────────┘                   │
                                                                            ▼
                                                                  即時儀表板 + 警報
```

### 核心功能

| 功能 | 說明 |
|:---|:---|
| 📊 **即時儀表板** | 每秒更新 RPM，使用雜湊比對減少 90% API 請求 |
| 🚨 **邊緣觸發警報** | 轉速異常時只發一次 @everyone，持續異常不重複 |
| ✅ **5 秒恢復確認** | 轉速恢復後須維持 5 秒才通知，防門檻跳動 |
| 🐶 **三層看門狗** | Bridge 離線（LWT）、USB 拔除、感測器當機，全覆蓋 |
| 🌐 **多伺服器廣播** | 一筆 MQTT 資料同步餵給所有綁定的 Discord |
| 🛡️ **防 429 退避** | 撞 API 速率限制時指數退避，不崩潰 |
| 🧹 **Bulk Delete** | 每批 100 條、間隔 1.5 秒清空頻道 |
| 📟 **OLED 錯誤恢復** | 硬體錯誤 30 秒後自動重試 |

### MQTT Topic 規劃

| Topic | 方向 | 說明 |
|:---|:---:|:---|
| `factory/machine_01/rpm` | Nano → Discord | 即時轉速資料 |
| `factory/machine_01/status` | 雙向 | 狀態控制（ONLINE/OFFLINE/OLED_ERROR） |
| `factory/machine_01/threshold/set` | Discord → Nano | 遠端設定門檻值 |

## 📋 前置需求

- Python 3.10+
- Discord Bot Token（[Discord Developer Portal](https://discord.com/developers/applications) 申請）
- （選用）MQTT Broker（HiveMQ Cloud 或自建）
- （選用）Arduino Nano 搭配 RPM 感測器

## 🚀 快速開始

```bash
# 1. 複製 .env.template 為 .env 並填入設定
copy .env.template .env

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 啟動網關（若有 Nano 硬體）
python bridge.py

# 4. 啟動 Discord Bot
python bot.py
```

或使用 `start.bat` 一鍵啟動兩項服務。

### 📦 安裝注意事項

- `.env` 檔案包含 Discord Token 與 MQTT 密碼，**請勿提交至 Git**
- 資料庫 `data.db` 會自動建立，**無須手動初始化**
- 若無硬體，僅啟動 `bot.py` 仍可測試 `/help`、`/config` 等指令

## 🧩 如何新增功能？

在 `cogs/` 目錄下新增一個 `.py` 檔案即可，框架會自動載入，**不用修改任何既有檔案**。

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

## 🔧 可用指令

| 指令 | 權限 | 說明 |
|:---|:---|:---|
| `/help` | 所有人 | 查看所有可用指令 |
| `/config` | 所有人 | 查看本伺服器設定 |
| `/admin-status` | 管理員 | 查看 Bot 狀態 |
| `/admin-reload` | 管理員 | 重新載入指定模組 |
| `/admin-list` | 管理員 | 列出所有模組 |
| `/status` | 所有人 | 召喚即時 RPM 儀表板 |
| `/threshold` | 所有人 | 設定警報門檻值 |
| `/info` | 所有人 | 查看系統資訊 |
| `/cleanup` | 管理員 | 清除舊儀表板 |
| `/nuke` | 管理員 | 清空頻道（Bulk Delete） |
| `/showcase` | 管理員 | 🚀 啟用專題展示導覽 |

## 📄 授權

本專案採用 **MIT License** — 詳見 [LICENSE](LICENSE) 檔案。
