from __future__ import annotations

from scott_claude.core.task.model import Task


# 功能：验证 Task.to_dict() 包含所有预期字段
# 设计：直接构造 Task，断言 to_dict() 的 key 集合，不依赖序列化格式
def test_task_to_dict_keys() -> None:
    task = Task(
        id=1,
        subject="test",
        description="desc",
        status="pending",
        blocked_by=[],
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
    )
    d = task.to_dict()
    assert set(d) == {"id", "subject", "description", "status", "blocked_by", "created_at", "updated_at"}


# 功能：验证 Task.from_dict() 能正确还原所有字段
# 设计：round-trip：to_dict → from_dict → 断言字段值相等
def test_task_roundtrip() -> None:
    task = Task(
        id=3, subject="write tests", description="cover all tools",
        status="in_progress", blocked_by=[1, 2],
        created_at="t1", updated_at="t2",
    )
    restored = Task.from_dict(task.to_dict())
    assert restored.id == 3
    assert restored.subject == "write tests"
    assert restored.status == "in_progress"
    assert restored.blocked_by == [1, 2]


# 功能：验证不同实例的 blocked_by 列表互不共享
# 设计：修改一个实例的列表，断言另一个实例不受影响
def test_task_blocked_by_not_shared() -> None:
    t1 = Task(id=1, subject="a", description="", status="pending",
              blocked_by=[], created_at="", updated_at="")
    t2 = Task(id=2, subject="b", description="", status="pending",
              blocked_by=[], created_at="", updated_at="")
    t1.blocked_by.append(99)
    assert t2.blocked_by == []
