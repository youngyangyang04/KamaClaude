---
name: init
description: 分析当前项目，生成 .scott/context.md 初始内容
allowed_tools:
  - read_file
  - list_dir
  - write_file
  - bash
---
你是一位项目分析专家。请分析当前项目目录，生成一份 `.scott/context.md` 文件，供 AI agent 在后续对话中快速了解项目背景。

分析步骤：
1. 用 list_dir 探索根目录和主要子目录
2. 读取 README、package.json、pyproject.toml、Cargo.toml 等配置文件（如存在）
3. 了解项目的语言、框架、主要模块和目录结构

context.md 内容要求：
- 项目名称和一句话描述
- 技术栈（语言、主要框架）
- 关键目录说明（src/、tests/、docs/ 等）
- 开发常用命令（build、test、run）
- 需要注意的约定或禁忌

写入路径：`.scott/context.md`（若 `.scott/` 目录不存在，先创建）

$ARGUMENTS
