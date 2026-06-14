# Git 操作指南

## 1. 初始化

```bash
# 克隆自己的 fork
git clone https://github.com/<你的用户名>/KamaClaude.git
cd KamaClaude

# 添加上游仓库（方便同步原作者更新）
git remote add upstream https://github.com/原作者/KamaClaude.git

# 验证远程仓库
git remote -v
# origin   → 你自己的 fork
# upstream → 原项目
```

## 2. 查看状态与日志

```bash
# 当前状态（改了什么文件、在哪个分支）
git status

# 当前分支所有提交历史
git log --oneline --all --graph

# 只看某个分支的提交
git log --oneline origin/stage/s0
```

## 3. 分支管理

```bash
# 查看所有分支（本地 + 远程）
git branch -a

# 切换到分支
git checkout stage/s0

# 创建新分支并切换
git checkout -b feature/my-feature

# 切换回 main
git checkout main

# 删除本地分支
git branch -d feature/my-feature
```

## 4. 同步原项目更新

```bash
# 获取 upstream 所有更新
git fetch upstream

# 在 main 上合并
git checkout main
git merge upstream/main

# 推送到你自己的 fork
git push origin main
```

## 5. 合并分支

```bash
# 把 stage/s0 合并到 main
git checkout main
git merge origin/stage/s0

# 如果有冲突：编辑器打开冲突文件，手动解决后
git add <冲突文件>
git commit -m "merge: 解决冲突"

# 推送
git push origin main
```

## 6. 临时保存与恢复修改

```bash
# 保存当前修改（不提交）
git stash

# 切换分支
git checkout stage/s0

# 恢复之前的修改
git stash pop

# 查看 stash 列表
git stash list

# 丢弃某个 stash
git stash drop <stash编号>
```

## 7. 提交修改

```bash
# 查看改了什么
git diff

# 暂存指定文件
git add src/kama_claude/core/app.py

# 提交
git commit -m "fix(core): 支持 Windows 平台的信号处理"

# 推送
git push origin main
```

## 8. 丢弃修改

```bash
# 丢弃某个文件的工作区修改
git checkout -- src/kama_claude/core/app.py

# 丢弃所有工作区修改
git checkout .
```

## 9. 常用分支策略

本项目使用以下分支命名：

| 分支 | 说明 |
|------|------|
| `main` | 主分支，最新稳定代码 |
| `origin/stage/s0` | S0 阶段开发分支 |
| `origin/stage/sN` | S1-N 阶段开发分支 |

操作原则：

- 在对应分支上开发（如 `origin/stage/s0`）
- 每个阶段完成后再合并到 `main`
- 不要直接修改 `main`，除非是修复跨阶段的问题
