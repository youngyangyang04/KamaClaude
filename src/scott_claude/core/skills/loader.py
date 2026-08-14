from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    system_prompt_template: str
    allowed_tools: list[str] = field(default_factory=list)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# 解析 Markdown skill 文本，提取 frontmatter 和正文 system prompt（不依赖文件名）
def parse_skill_text(text: str) -> Skill:
    name = ""
    description = ""
    allowed_tools: list[str] = []
    body = text

    m = _FRONTMATTER_RE.match(text)
    if m:
        front = m.group(1)
        body = text[m.end():]
        lines = front.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("name:"):
                name = stripped[len("name:"):].strip().strip('"').strip("'")
            elif stripped.startswith("description:"):
                val = stripped[len("description:"):].strip().strip('"').strip("'")
                # YAML 块标量：> (折叠) 或 | (保留换行)，后续缩进行是内容
                if val in (">", "|"):
                    fold = val == ">"
                    parts: list[str] = []
                    i += 1
                    while i < len(lines) and lines[i].startswith((" ", "\t")):
                        parts.append(lines[i].strip())
                        i += 1
                    description = (" ".join(parts) if fold else "\n".join(parts)).strip()
                    continue
                else:
                    description = val
            elif stripped.startswith("allowed_tools:"):
                pass
            elif stripped.startswith("- "):
                allowed_tools.append(stripped[2:].strip())
            i += 1

    return Skill(
        name=name,
        description=description,
        system_prompt_template=body.strip(),
        allowed_tools=allowed_tools,
    )


# 解析 Markdown skill 文件；frontmatter 缺 name 时回退用文件名
def _parse_skill_file(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    skill = parse_skill_text(text)
    if not skill.name:
        skill.name = path.stem
    return skill


# 按三级优先级（项目本地 > 用户全局 > 内建）查找并解析 skill
class SkillLoader:
    _BUILTIN_DIR = Path(__file__).parent / "builtin"

    # 按优先级查找 skill 文件；未找到返回 None
    def resolve(self, name: str) -> Skill | None:
        for path in self._search_paths(name):
            if path.exists():
                try:
                    return _parse_skill_file(path)
                except Exception:
                    return None
        return None

    # 返回候选路径列表，同时支持扁平文件（name.md）和目录式（name/SKILL.md）两种格式
    def _search_paths(self, name: str) -> list[Path]:
        dirs = [
            Path(".scott/skills"),
            Path("~/.scott/skills").expanduser(),
            self._BUILTIN_DIR,
        ]
        paths: list[Path] = []
        for d in dirs:
            paths.append(d / f"{name}.md")
            paths.append(d / name / "SKILL.md")
        return paths

    # 按优先级返回第一个存在的 skill 文件路径；未找到返回 None
    def resolve_path(self, name: str) -> Path | None:
        for path in self._search_paths(name):
            if path.exists():
                return path
        return None

    # 列出所有可用 skill 名称（内建 + 用户全局 + 项目本地，去重后以项目本地覆盖为准）
    def list_all(self) -> list[str]:
        seen: dict[str, None] = {}
        for d in [
            self._BUILTIN_DIR,
            Path("~/.scott/skills").expanduser(),
            Path(".scott/skills"),
        ]:
            if d.exists():
                for f in sorted(d.glob("*.md")):
                    seen[f.stem] = None
                for f in sorted(d.glob("*/SKILL.md")):
                    seen[f.parent.name] = None
        return list(seen)

    # 列出所有可用 Skill 对象（含描述），项目本地覆盖同名内建
    def list_all_skills(self) -> list[Skill]:
        seen: dict[str, Skill] = {}
        for d in [
            self._BUILTIN_DIR,
            Path("~/.scott/skills").expanduser(),
            Path(".scott/skills"),
        ]:
            if d.exists():
                for f in sorted(d.glob("*.md")):
                    try:
                        skill = _parse_skill_file(f)
                        seen[skill.name] = skill
                    except Exception:
                        pass
                for f in sorted(d.glob("*/SKILL.md")):
                    try:
                        skill = _parse_skill_file(f)
                        seen[skill.name] = skill
                    except Exception:
                        pass
        return list(seen.values())

    # 将 $ARGUMENTS 替换为用户传入的参数字符串
    def render_prompt(self, skill: Skill, arguments: str) -> str:
        return skill.system_prompt_template.replace("$ARGUMENTS", arguments)
