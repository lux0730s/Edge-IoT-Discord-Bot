"""
Edge IoT RPM Monitor — MQTT 服務模組
負責與 MQTT Broker 的連線、訂閱與發布，透過回呼通知上層。
"""

import ssl
import logging
from typing import Callable, Awaitable

import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
    TOPIC_RPM, TOPIC_STATUS, TOPIC_CMD_THRESHOLD,
)

log = logging.getLogger(__name__)

# 定義回呼型別
MqttMessageHandler = Callable[[str, str], Awaitable[None]]


class MqttService:
    """
    封裝 MQTT 連線邏輯。
    使用方式：
        service = MqttService(on_message=my_async_handler, loop=asyncio_loop)
        service.start()
    """

    def __init__(self, on_message: MqttMessageHandler, loop):
        self._on_message = on_message
        self._loop = loop
        self._client: mqtt.Client | None = None

    def start(self) -> None:
        """建立連線並開始監聽。"""
        if not MQTT_BROKER:
            log.warning("未設定 MQTT_BROKER，跳過 MQTT 連線")
            return

        self._client = mqtt.Client(client_id="discord_bot_01")
        self._client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        self._client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_raw_message
        self._client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        """斷開連線並停止迴圈。"""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def publish_threshold(self, value: int) -> None:
        """發布門檻設定至 MQTT。"""
        if not self._client:
            return
        try:
            self._client.publish(TOPIC_CMD_THRESHOLD, str(value), qos=1)
            log.info(f"📤 門檻指令已發布至 MQTT: {value}")
        except Exception as e:
            log.error(f"發布門檻失敗: {e}")

    # ── 內部回呼 ──

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("✅ MQTT 已連線至 Broker")
            client.subscribe(TOPIC_RPM)
            client.subscribe(TOPIC_STATUS)
        else:
            log.error(f"MQTT 連線失敗，rc={rc}")

    def _on_raw_message(self, client, userdata, msg):
        """將 MQTT 執行緒的訊息轉發至 asyncio 事件迴圈。"""
        import asyncio
        asyncio.run_coroutine_threadsafe(
            self._on_message(msg.topic, msg.payload.decode("utf-8")),
            self._loop,
        )
