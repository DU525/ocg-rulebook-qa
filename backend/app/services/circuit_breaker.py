"""Circuit Breaker——熔断器模式，防止连续失败导致雪崩"""
import time
import logging
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # 正常状态，请求通过
    OPEN = "open"           # 熔断状态，直接拒绝
    HALF_OPEN = "half_open" # 半开状态，允许一次试探


class CircuitBreaker:
    """熔断器实现
    状态转换：
    CLOSED → OPEN：连续失败达到阈值
    OPEN → HALF_OPEN：等待时间过后
    HALF_OPEN → CLOSED：试探成功
    HALF_OPEN → OPEN：试探失败
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,      # 连续失败阈值
        recovery_timeout: int = 60,       # 恢复等待时间（秒）
        success_threshold: int = 1,       # 半开状态成功次数要求
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            # 检查是否已过恢复等待时间
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(f"[{self.name}] Circuit breaker → HALF_OPEN")
        return self._state

    def record_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"[{self.name}] Circuit breaker → CLOSED (recovered)")
        else:
            self._failure_count = 0

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"[{self.name}] Circuit breaker → OPEN (probe failed)")
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"[{self.name}] Circuit breaker → OPEN "
                f"(failures={self._failure_count}/{self.failure_threshold})"
            )

    def can_execute(self) -> bool:
        return self.state != CircuitState.OPEN

    def __call__(self, f):
        """装饰器使用"""
        @wraps(f)
        def decorated(*args, **kwargs):
            if not self.can_execute():
                raise CircuitBreakerOpenError(
                    f"[{self.name}] Circuit breaker is OPEN. "
                    f"Wait {self.recovery_timeout}s for recovery."
                )

            try:
                result = f(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise

        return decorated

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "threshold": self.failure_threshold,
        }


class CircuitBreakerOpenError(Exception):
    """熔断器打开时的异常"""
    pass
