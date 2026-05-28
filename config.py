"""
Edge IoT RPM Monitor — 設定模組
統一管理所有全域設定與常數。
注意：
- 各伺服器自訂的設定（門檻值、頻道等）已移至資料庫
- 此檔案只放不會變的全局常數
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── Discord ──
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

# ── MQTT ──
MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 8883))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")

# ── MQTT Topics ──
TOPIC_RPM = "factory/machine_01/rpm"
TOPIC_STATUS = "factory/machine_01/status"
TOPIC_CMD_THRESHOLD = "factory/machine_01/threshold/set"

# ── 行為常數 ──
ALERT_COOLDOWN = 60           # 警報冷卻秒數（展示用縮短為 60 秒）
WATCHDOG_THRESHOLD = 60       # 看門狗判定離線秒數
DASHBOARD_INTERVAL = 5        # 儀表板更新間隔
OLED_RESET_TIMEOUT = 30       # OLED 自動恢復秒數
STARTUP_GRACE = 10            # 啟動寬限期
