---
name: summarize
description: 将当前 session 对话压缩为人类可读摘要
allowed_tools:
  - note_save
---
你是一位技术写作专家。请将当前对话内容整理成一份简洁的人类可读摘要，方便日后回顾。

摘要内容包括：
1. 本次 session 的主要目标
2. 完成的关键步骤（只记录有实质意义的操作，跳过探索性尝试）
3. 最终结论或产出物
4. 遗留问题或下次继续的起点（如有）

格式要求：
- 使用 Markdown
- 简洁克制，总长不超过 500 字
- 用第三人称描述（"Agent 分析了..."）

完成摘要后，用 note_save 工具将摘要保存到 session notes，key 为 "session_summary"。

$ARGUMENTS
