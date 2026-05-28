"""
Edge IoT Discord Bot Framework — 企業級日誌系統
提供結構化、可輪替、多層級的日誌，便於除錯與稽核。
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# ── 預設值 ──
DEFAULT_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.environ.get("LOG_DIR", "logs")
LOG_FILE = os.environ.get("LOG_FILE", os.path.join(LOG_DIR, "bot.log"))
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str = DEFAULT_LEVEL,
    log_file: str | None = LOG_FILE,
    console: bool = True,
) -> logging.Logger:
    """
    初始化日誌系統。
    - 檔案輸出：自動輪替（最大 5MB，保留 5 個備份）
    - 終端輸出：彩色，開發友善
    """
    # 確保日誌目錄存在
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

    # 根 Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # 清除已有 handlers（避免重複初始化）
    root_logger.handlers.clear()

    # 格式化器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # ── 檔案 Handler（自動輪替）──
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, level, logging.INFO))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # ── 終端 Handler ──
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level, logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 避免 discord.py 的 debug 訊息過於嘈雜
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("paho").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"📋 日誌系統已初始化 (level={level}, file={log_file})")
    return logger
