"""
Circuit breaker implementation for handling backpressure and failures.

Provides circuit breaker pattern to prevent cascade failures when
downstream systems (Kafka) are unavailable or overloaded.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Failing, blocking requests
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5           # Failed requests to open circuit
    success_threshold: int = 3           # Successful requests to close circuit
    timeout: float = 60.0               # Seconds to wait before trying half-open
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures


class CircuitBreakerMetrics:
    """Circuit breaker metrics and statistics."""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.circuit_opened_count = 0
        self.circuit_closed_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        
    def record_success(self):
        """Record a successful request."""
        self.total_requests += 1
        self.successful_requests += 1
        self.last_success_time = datetime.now()
    
    def record_failure(self):
        """Record a failed request."""
        self.total_requests += 1
        self.failed_requests += 1
        self.last_failure_time = datetime.now()
    
    def record_circuit_opened(self):
        """Record circuit opening."""
        self.circuit_opened_count += 1
    
    def record_circuit_closed(self):
        """Record circuit closing."""
        self.circuit_closed_count += 1
    
    @property
    def failure_rate(self) -> float:
        """Calculate current failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "failure_rate": round(self.failure_rate * 100, 2),
            "circuit_opened_count": self.circuit_opened_count,
            "circuit_closed_count": self.circuit_closed_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for handling downstream service failures.
    
    The circuit breaker monitors the failure rate of operations and can be in
    one of three states: CLOSED (normal), OPEN (failing), or HALF_OPEN (testing).
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            Any exception raised by the function
        """
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info("Circuit breaker moving to HALF_OPEN state")
                else:
                    self.metrics.record_failure()
                    raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            # Record success
            await self._record_success()
            return result
            
        except self.config.expected_exception as e:
            await self._record_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.timeout
    
    async def _record_success(self):
        """Record successful operation."""
        async with self._lock:
            self.success_count += 1
            self.metrics.record_success()
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.success_count >= self.config.success_threshold:
                    self._reset()
                    logger.info("Circuit breaker CLOSED after successful recovery")
    
    async def _record_failure(self):
        """Record failed operation."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            self.metrics.record_failure()
            
            if self.state == CircuitBreakerState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self._trip()
                    logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self._trip()
                logger.warning("Circuit breaker reopened during HALF_OPEN test")
    
    def _trip(self):
        """Trip the circuit breaker to OPEN state."""
        self.state = CircuitBreakerState.OPEN
        self.success_count = 0
        self.metrics.record_circuit_opened()
    
    def _reset(self):
        """Reset the circuit breaker to CLOSED state."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.metrics.record_circuit_closed()
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is in CLOSED state."""
        return self.state == CircuitBreakerState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is in OPEN state."""
        return self.state == CircuitBreakerState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is in HALF_OPEN state."""
        return self.state == CircuitBreakerState.HALF_OPEN
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": datetime.fromtimestamp(self.last_failure_time).isoformat() if self.last_failure_time else None,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            },
            "metrics": self.metrics.get_stats()
        }


class AsyncCircuitBreaker:
    """Async context manager wrapper for circuit breaker."""
    
    def __init__(self, circuit_breaker: CircuitBreaker):
        self.circuit_breaker = circuit_breaker
    
    async def __aenter__(self):
        if self.circuit_breaker.is_open and not self.circuit_breaker._should_attempt_reset():
            raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        return self.circuit_breaker
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.circuit_breaker._record_success()
        elif issubclass(exc_type, self.circuit_breaker.config.expected_exception):
            await self.circuit_breaker._record_failure()
        return False  # Don't suppress exceptions


def circuit_breaker_decorator(config: Optional[CircuitBreakerConfig] = None):
    """
    Decorator to add circuit breaker functionality to functions.
    
    Args:
        config: Circuit breaker configuration
        
    Returns:
        Decorated function with circuit breaker protection
    """
    breaker = CircuitBreaker(config)
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(breaker.call(func, *args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            async_wrapper.circuit_breaker = breaker
            return async_wrapper
        else:
            sync_wrapper.circuit_breaker = breaker
            return sync_wrapper
    
    return decorator


# Example usage and testing
if __name__ == "__main__":
    import random
    
    async def unreliable_service():
        """Simulate an unreliable service."""
        if random.random() < 0.7:  # 70% failure rate
            raise Exception("Service unavailable")
        return "Success"
    
    async def test_circuit_breaker():
        """Test circuit breaker functionality."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=5.0
        )
        breaker = CircuitBreaker(config)
        
        for i in range(10):
            try:
                result = await breaker.call(unreliable_service)
                print(f"Request {i+1}: {result}")
            except (Exception, CircuitBreakerOpenError) as e:
                print(f"Request {i+1}: Failed - {e}")
            
            print(f"Circuit state: {breaker.state.value}")
            await asyncio.sleep(1)
        
        print("\nFinal statistics:")
        print(breaker.get_status())
    
    # Run test
    # asyncio.run(test_circuit_breaker())