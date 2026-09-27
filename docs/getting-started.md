# 上手指南

## 图形界面

首个本地 App 已提供：在 PowerShell 中执行 `.\Start-PGOS.ps1`。初次体验用 `.\Start-PGOS.ps1 -Demo`；已有 Python 的环境可用 `python -B -m app.server`。详细步骤、Ollama 配置和限制见 [App 使用指南](app-v1.md)。

## 本地使用

准备 Python 3.10+，在项目根目录执行 `python scripts/pgos.py init`。不需安装第三方包。

命令将空白模板复制为：

| 私有路径（相对 private/workspace） | 用途 |
| --- | --- |
| goals/current.md | 当前目标 |
| learning/current.md | 学习记录 |
| knowledge/current.md | 知识笔记 |
| journal/current.md | 单次反思 |
| reflections/current.md | 周复盘 |
| habits/current.md | 习惯观察 |
| prompts/current.md | 私人提示词版本 |
| memory/current-model.md | 当前个人理解 |

`current.md` 是起始文件；新增周期时另存为日期或主题文件，保留旧记录。初始化重复执行不会覆盖记录；它不导入旧日记。

## 与 Agent 配合

让 Agent 先读 AGENTS.md，再选择一个 prompts 文件。明确输入文件、希望解决的问题、允许读取范围和输出位置。例如：

> 使用周复盘提示词，仅阅读我提供的本周学习记录和目标。区分计划、执行和结果，把复盘保存到 private/workspace/reflections/ 本周文件，不更新长期记忆。

只有你愿意向所用服务分享的材料才交给在线 Agent。本地文件隔离不能限制 Agent 或云服务的实际数据访问；需另行配置工具权限。

## 从旧项目迁移

备份旧目录后，将私人资料保存在 private/legacy 下。保留原文件结构和来源链接；只逐项转移需要继续维护的资料到 private/workspace。公共示例从零编写，不复制旧经历。

发布前依照 [发布清单](release-checklist.md)，使用导出副本建立新仓库。
