"""
Edge IoT - MQTT Serial Bridge
功能：將 Arduino Nano (COM Port) 與 HiveMQ Cloud 雙向串接
"""

import os
import time
import logging
import serial
import ssl
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ─── 基本設定 ─────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

COM_PORT      = os.environ.get("COM_PORT", "COM4")
BAUD_RATE     = int(os.environ.get("BAUD_RATE", 9600))

MQTT_BROKER   = os.environ.get("MQTT_BROKER")
MQTT_PORT     = int(os.environ.get("MQTT_PORT", 8883))
MQTT_USER     = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")

# ─── MQTT Topic 規劃 ──────────────────────────────────
TOPIC_RPM           = "factory/machine_01/rpm"
TOPIC_STATUS        = "factory/machine_01/status"
TOPIC_CMD_THRESHOLD = "factory/machine_01/threshold/set"

ser = None

# ─── MQTT 回呼函式 ────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info(f"✅ 成功連線至 MQTT Broker ({MQTT_BROKER})")
        client.subscribe(TOPIC_CMD_THRESHOLD)
        client.publish(TOPIC_STATUS, "ONLINE", retain=True)
    else:
        log.error(f"❌ MQTT 連線失敗，錯誤碼: {rc}")

def on_disconnect(client, userdata, rc):
    log.warning("⚠️ MQTT 已斷線，將自動嘗試重連...")

def on_message(client, userdata, msg):
    global ser
    topic = msg.topic
    payload = msg.payload.decode("utf-8")

    if topic == TOPIC_CMD_THRESHOLD:
        log.info(f"📥 收到雲端門檻設定指令: {payload} RPM")
        # 【修正】加上 try-except 防禦：避免在正好拔出 USB 的瞬間，嘗試寫入導致程式閃退 (Race Condition 保護)
        if ser and ser.is_open:
            try:
                command = f"THRESHOLD:{int(payload)}\n"
                ser.write(command.encode("utf-8"))
                log.info(f"📤 已寫入 COM Port: {command.strip()}")
            except serial.SerialException:
                log.warning("⚠️ 寫入時發生 Serial 異常 (忽略，交由主迴圈重連)")
            except Exception as e:
                log.error(f"❌ Serial 寫入錯誤: {e}")
        else:
            log.warning("⚠️ 忽略指令：COM Port 尚未連線")

# ─── 系統啟動與主迴圈 ──────────────────────────────────
def setup_mqtt():
    client = mqtt.Client(client_id="bridge_nano_01")
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    
    # 遺囑機制：若網關程式崩潰或電腦斷網，雲端會自動收到 OFFLINE
    client.will_set(TOPIC_STATUS, "OFFLINE", qos=1, retain=True)
    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    log.info("連線至 MQTT Broker 中...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()
    return client

def main_loop(client):
    global ser
    retry_delay = 2

    while True:
        # 1. 維護 COM Port 連線狀態
        if ser is None or not ser.is_open:
            try:
                ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
                ser.reset_input_buffer()  # 【修正】連線後清空緩衝區，避免殘留上次斷線的截斷亂碼
                log.info(f"✅ Serial 連線成功: {COM_PORT}")
                client.publish(TOPIC_STATUS, "SENSOR_ONLINE", qos=1)
                retry_delay = 2
            except serial.SerialException:
                log.warning(f"⚠️ COM Port 連線失敗，{retry_delay} 秒後重試...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
                continue

        # 2. 讀取感測器資料
        try:
            raw = ser.readline()
            if not raw:
                time.sleep(0.05)
                continue
                
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            if line == "OLED_ERROR":
                log.warning("⚠️ 收到 Nano 硬體異常報告 (OLED_ERROR)")
                client.publish(TOPIC_STATUS, "OLED_ERROR", qos=1)
                continue

            if line.startswith("RPM:"):
                parts = dict(p.split(":", 1) for p in line.split(",") if ":" in p)
                rpm_str = parts.get("RPM", "-1")
                try:
                    rpm_val = int(rpm_str)
                    if 0 <= rpm_val <= 100000:
                        client.publish(TOPIC_RPM, str(rpm_val), qos=0)
                except ValueError:
                    pass
                    
        except serial.SerialException as e:
            log.error(f"❌ COM Port 讀取錯誤 (設備拔除): {e}")
            ser.close()
            ser = None
            client.publish(TOPIC_STATUS, "SENSOR_OFFLINE", qos=1)
        except Exception as e:
            log.error(f"❌ 未預期錯誤: {e}")
            time.sleep(1)

if __name__ == "__main__":
    if not MQTT_BROKER:
        log.error("請在 .env 中設定 MQTT 相關變數！")
        exit(1)
        
    mqtt_client = setup_mqtt()
    try:
        main_loop(mqtt_client)
    except KeyboardInterrupt:
        log.info("🛑 系統手動關閉...")
        mqtt_client.publish(TOPIC_STATUS, "OFFLINE", retain=True)
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        if ser and ser.is_open:
            ser.close()