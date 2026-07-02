"""BaseAgent 超时/重试/降级测试"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.base_agent import BaseAgent
from models.schemas import AgentResult


class SlowAgent(BaseAgent):
    """模拟卡死的Agent：执行时间远超timeout"""

    def __init__(self, timeout: float = 0.2):
        super().__init__(name="slow", timeout=timeout, max_retries=2)

    async def _execute(self, **kwargs) -> AgentResult:
        await asyncio.sleep(10)
        return AgentResult(agent_name=self.name, success=True)


class FastAgent(BaseAgent):
    """正常Agent：在timeout内完成"""

    def __init__(self):
        super().__init__(name="fast", timeout=1.0, max_retries=2)

    async def _execute(self, **kwargs) -> AgentResult:
        await asyncio.sleep(0.01)
        return AgentResult(agent_name=self.name, success=True)


class FlakyAgent(BaseAgent):
    """前N次失败、之后成功的Agent，验证重试"""

    def __init__(self, fail_times: int):
        super().__init__(name="flaky", timeout=1.0, max_retries=3)
        self.fail_times = fail_times
        self.attempts = 0

    async def _execute(self, **kwargs) -> AgentResult:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise RuntimeError("transient error")
        return AgentResult(agent_name=self.name, success=True)


def test_timeout_triggers_fallback():
    """超时的Agent应返回降级结果而不是无限等待"""
    import time

    agent = SlowAgent(timeout=0.2)
    t0 = time.perf_counter()
    result = asyncio.run(agent.run())
    elapsed = time.perf_counter() - t0

    assert result.success is False, "超时后应返回降级结果"
    assert result.confidence == 0.0
    # 2次重试 × 0.2s超时 + 退避间隔，应远小于_execute本身的10s
    assert elapsed < 5, f"超时控制未生效，耗时 {elapsed:.1f}s"


def test_fast_agent_unaffected():
    """timeout内完成的Agent不受影响"""
    agent = FastAgent()
    result = asyncio.run(agent.run())
    assert result.success is True


def test_retry_then_succeed():
    """瞬时错误应通过重试恢复"""
    agent = FlakyAgent(fail_times=2)
    result = asyncio.run(agent.run())
    assert result.success is True
    assert agent.attempts == 3


def test_all_retries_exhausted():
    """重试次数耗尽后走降级"""
    agent = FlakyAgent(fail_times=10)
    result = asyncio.run(agent.run())
    assert result.success is False
    assert result.error is not None


if __name__ == "__main__":
    test_timeout_triggers_fallback()
    test_fast_agent_unaffected()
    test_retry_then_succeed()
    test_all_retries_exhausted()
    print("All BaseAgent tests passed!")
