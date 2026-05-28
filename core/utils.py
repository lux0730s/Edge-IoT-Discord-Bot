"""
Edge IoT Discord Bot Framework — 常用小工具
提供格式化、驗證等通用函式。
"""

import time
from typing import Any


def format_uptime(startup_time: float) -> str:
    """將啟動時間戳記轉為人類可讀的運作時間。"""
    seconds = int(time.time() - startup_time)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days} 天")
    if hours:
        parts.append(f"{hours} 小時")
    if minutes:
        parts.append(f"{minutes} 分")
    parts.append(f"{seconds} 秒")
    return " ".join(parts)


def validate_rpm(value: int) -> str | None:
    """
    驗證 RPM 值是否合法。
    回傳 None 代表合法，回傳字串代表錯誤訊息。
    """
    if not isinstance(value, int):
        return "請輸入整數"
    if value < 0:
        return "RPM 不能為負數"
    if value > 99999:
        return "RPM 值過大（上限 99999）"
    return None


def parse_bool(value: str | bool) -> bool:
    """將常見的布林值字串解析為 bool。"""
    if isinstance(value, bool):
        return value
    return value.strip().lower() in ("true", "1", "yes", "on", "y")


def safe_int(value: Any, default: int = 0) -> int:
    """安全轉換為整數，轉換失敗回傳預設值。"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
