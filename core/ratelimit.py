"""
Edge IoT Discord Bot Framework — 速率限制
防止使用者短時間內過度發送指令，保護 Bot 不被濫用。
"""

import time
import logging
from collections import defaultdict

log = logging.getLogger(__name__)

# ── 預設限制 ──
DEFAULT_MAX_CALLS = 10       # 允許次數
DEFAULT_WINDOW = 60          # 時間窗口（秒）


class RateLimiter:
    """
    簡單的速率限制器。
    記錄每個使用者的呼叫時間，若在指定時間窗口內超過次數則阻擋。
    """

    def __init__(self, max_calls: int = DEFAULT_MAX_CALLS, window: int = DEFAULT_WINDOW):
        self._max_calls = max_calls
        self._window = window
        self._records: dict[int, list[float]] = defaultdict(list)

    def check(self, user_id: int) -> bool:
        """
        檢查使用者是否超過速率限制。
        回傳 True 代表允許，False 代表被限制。
        """
        now = time.time()
        records = self._records[user_id]

        # 清除過期的記錄
        cutoff = now - self._window
        self._records[user_id] = [t for t in records if t > cutoff]

        # 檢查是否超限
        if len(self._records[user_id]) >= self._max_calls:
            log.warning(f"⚠️ 速率限制觸發: user_id={user_id}, count={len(self._records[user_id])}")
            return False

        # 記錄此次呼叫
        self._records[user_id].append(now)
        return True

    def get_remaining(self, user_id: int) -> int:
        """取得使用者剩餘的可用次數。"""
        now = time.time()
        cutoff = now - self._window
        active = [t for t in self._records.get(user_id, []) if t > cutoff]
        remaining = self._max_calls - len(active)
        return max(0, remaining)


# ── 全域實例 ──
rate_limiter = RateLimiter()
