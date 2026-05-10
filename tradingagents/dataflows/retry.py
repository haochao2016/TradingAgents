"""Generic retry wrapper used by data-fetching modules."""
import time
import logging

logger = logging.getLogger(__name__)


def with_retry(func, max_retries=5, base_delay=1.0, name="call"):
    """Call *func* with retry + exponential backoff on any exception.

    Logs each attempt number. After *max_retries* failures, re-raises
    the last exception so the caller's existing try/except catches it.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    f"[{name}] 第 {attempt}/{max_retries} 轮失败, "
                    f"{delay:.0f}s 后重试: {e}"
                )
                time.sleep(delay)
            else:
                logger.error(f"[{name}] 全部 {max_retries} 轮重试均失败: {e}")
                raise
