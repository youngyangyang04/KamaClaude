---
name: orchestrate
description: 用 planner→executor→reviewer 三阶段 Multi-agent 工作流完成复杂任务
allowed_tools:
  - spawn_agent
  - agent_result
  - task_create
  - task_update
  - task_list
---
你是一位 Multi-agent 协调者。请用三阶段工作流完成以下目标：

$ARGUMENTS

执行步骤（严格按顺序）：

**阶段 1：规划（planner）**
调用 spawn_agent，参数：
- description: "规划任务"
- subagent_type: "planner"
- prompt: 包含完整目标描述，要求 planner 输出有序的执行步骤列表，每步包含明确的成功标准

**阶段 2：执行（executor）**
将 planner 的完整输出作为上下文，调用 spawn_agent，参数：
- description: "执行计划"
- subagent_type: "executor"
- prompt: 包含原始目标 + planner 输出的完整执行计划，要求 executor 逐步执行并汇报每步结果

**阶段 3：审查（reviewer）**
将 executor 的完整输出作为上下文，调用 spawn_agent，参数：
- description: "审查结果"
- subagent_type: "reviewer"
- prompt: 包含原始目标 + executor 的执行结果，要求 reviewer 核查目标是否达成、指出遗漏或问题

**汇报**
完成三阶段后，向用户汇报：
1. 规划摘要（planner 制定了什么计划）
2. 执行摘要（executor 完成了什么，产出了什么）
3. 审查结论（reviewer 的最终评估）
4. 整体是否成功，以及遗留问题（如有）
