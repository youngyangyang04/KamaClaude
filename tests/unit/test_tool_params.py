from __future__ import annotations

import pytest
from pydantic import ValidationError

from scott_claude.core.tools.builtin.bash import BashParams
from scott_claude.core.tools.builtin.list_dir import ListDirParams
from scott_claude.core.tools.builtin.note_save import NoteSaveParams
from scott_claude.core.tools.builtin.read_file import ReadFileParams
from scott_claude.core.tools.builtin.write_file import WriteFileParams


# 功能：验证 BashParams 接受合法参数，缺省 timeout 为 60
# 设计：直接 model_validate 字典，覆盖必填字段存在和可选字段默认值两种路径
def test_bash_params_valid() -> None:
    p = BashParams.model_validate({"command": "echo hi"})
    assert p.command == "echo hi"
    assert p.timeout == 60


# 功能：验证 BashParams timeout 上限被 pydantic le=120 约束
# 设计：传入 200 预期 ValidationError，确保不需要工具内部手动 min()
def test_bash_params_timeout_clamped() -> None:
    with pytest.raises(ValidationError):
        BashParams.model_validate({"command": "sleep 200", "timeout": 200})


# 功能：验证 BashParams 缺少 command 时抛 ValidationError
# 设计：传空字典触发 required 字段缺失，覆盖 schema_error 的核心触发条件
def test_bash_params_missing_command() -> None:
    with pytest.raises(ValidationError):
        BashParams.model_validate({})


# 功能：验证 BashParams command 为非字符串时抛 ValidationError
# 设计：传 int 触发类型校验，对应 agent 误传错误类型的情景
def test_bash_params_wrong_type() -> None:
    with pytest.raises(ValidationError):
        BashParams.model_validate({"command": 123})


# 功能：验证 BashParams 忽略额外字段（extra="ignore"）
# 设计：LLM 有时会多传字段，extra="ignore" 防止 ValidationError，保证鲁棒性
def test_bash_params_extra_ignored() -> None:
    p = BashParams.model_validate({"command": "ls", "unknown_field": "x"})
    assert p.command == "ls"


# 功能：验证 ReadFileParams 接受合法路径字符串
# 设计：最小合法输入，断言 path 原样保留
def test_read_file_params_valid() -> None:
    p = ReadFileParams.model_validate({"path": "README.md"})
    assert p.path == "README.md"


# 功能：验证 ReadFileParams path 为整数时抛 ValidationError
# 设计：覆盖 LLM 传 int 路径的异常场景，对应 schema_error 分类
def test_read_file_params_wrong_type() -> None:
    with pytest.raises(ValidationError):
        ReadFileParams.model_validate({"path": 42})


# 功能：验证 WriteFileParams 需要 path 和 content 两个必填字段
# 设计：分别缺一个字段，覆盖两个 required 字段的独立缺失路径
def test_write_file_params_missing_fields() -> None:
    with pytest.raises(ValidationError):
        WriteFileParams.model_validate({"path": "out.txt"})  # missing content
    with pytest.raises(ValidationError):
        WriteFileParams.model_validate({"content": "hello"})  # missing path


# 功能：验证 WriteFileParams 合法输入原样保留
# 设计：完整输入，断言两个字段均正确赋值
def test_write_file_params_valid() -> None:
    p = WriteFileParams.model_validate({"path": "out.txt", "content": "hello"})
    assert p.path == "out.txt"
    assert p.content == "hello"


# 功能：验证 ListDirParams 全部使用默认值时合法
# 设计：空字典触发两个字段的默认值路径，断言 path="." max_depth=2
def test_list_dir_params_defaults() -> None:
    p = ListDirParams.model_validate({})
    assert p.path == "."
    assert p.max_depth == 2


# 功能：验证 ListDirParams max_depth 超过上限时抛 ValidationError
# 设计：传 le=4 边界外的值 5，确保不需要工具内手动 min()
def test_list_dir_params_max_depth_exceeded() -> None:
    with pytest.raises(ValidationError):
        ListDirParams.model_validate({"max_depth": 5})


# 功能：验证 NoteSaveParams 接受合法 content 字符串
# 设计：最小合法输入，断言 content 原样保留
def test_note_save_params_valid() -> None:
    p = NoteSaveParams.model_validate({"content": "Python 3.12"})
    assert p.content == "Python 3.12"


# 功能：验证 NoteSaveParams 缺少 content 时抛 ValidationError
# 设计：传空字典触发 required 字段缺失，覆盖空调用场景
def test_note_save_params_missing_content() -> None:
    with pytest.raises(ValidationError):
        NoteSaveParams.model_validate({})
