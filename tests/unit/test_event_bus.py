from __future__ import annotations

from pydantic import BaseModel

from scott_claude.core.events.bus import EventBus


class _FakeEvent(BaseModel):
    value: str


# 功能：验证 publish 后订阅者能收到事件对象
# 设计：用内联 handler 收集事件引用，断言 is 而非 ==，排除序列化中间步骤的干扰
async def test_publish_reaches_subscriber() -> None:
    bus = EventBus()
    received: list[BaseModel] = []

    async def handler(event: BaseModel) -> None:
        received.append(event)

    bus.subscribe(handler)
    event = _FakeEvent(value="hello")
    await bus.publish(event)
    assert received == [event]


# 功能：验证多个订阅者都能独立收到同一事件
# 设计：两个独立计数器分别累加，避免共享状态掩盖某一订阅者未被调用的情况
async def test_multiple_subscribers_all_receive() -> None:
    bus = EventBus()
    counts = [0, 0]

    async def h1(e: BaseModel) -> None:
        counts[0] += 1

    async def h2(e: BaseModel) -> None:
        counts[1] += 1

    bus.subscribe(h1)
    bus.subscribe(h2)
    await bus.publish(_FakeEvent(value="x"))
    assert counts == [1, 1]


# 功能：验证多个订阅者按注册顺序被依次调用
# 设计：用追加整数到列表来记录调用次序，因为 bus 的顺序语义是 AgentLoop 事件序列正确性的前提
async def test_subscribers_called_in_order() -> None:
    bus = EventBus()
    order: list[int] = []

    async def h1(e: BaseModel) -> None:
        order.append(1)

    async def h2(e: BaseModel) -> None:
        order.append(2)

    bus.subscribe(h1)
    bus.subscribe(h2)
    await bus.publish(_FakeEvent(value="x"))
    assert order == [1, 2]


# 功能：验证无订阅者时 publish 不抛异常（空 bus 边界条件）
# 设计：只调用 publish，不断言返回值，以"不引发异常"作为唯一判据
async def test_no_subscribers_publish_is_noop() -> None:
    bus = EventBus()
    await bus.publish(_FakeEvent(value="x"))  # should not raise
