# Personal Growth OS

一个利用 AI Agent 辅助个人成长管理的开源框架。用 Markdown 模板、可追溯的记录和明确的工作流程，连接目标、学习、知识、行动与复盘。

这是 Markdown 文件式工作系统，包含首个 Windows 本地 App、初始化、隐私检查和公开导出工具。普通记录与搜索完全离线；本地 Ollama 分析需明确选择输入并主动触发，没有在线账户或自动云端调用。

## 核心理念

- 把成长过程系统化：目标关联行动，行动关联反馈，复盘推动下一次调整。
- 用 AI 辅助规划与复盘：保留人的选择权，区分事实、推断和建议。
- 建立长期知识资产：记录可以迁移、比较和修正，不依赖单一服务商。
- 私人资料默认保留在本地：公共方法与个人数据分开存储。

## 功能

| 模块 | 用途 | 入口 |
| --- | --- | --- |
| Goal Management | 定义目标、验收证据与下一步 | [目标模板](templates/goals-template.md) |
| Learning Tracker | 记录练习、产出与反馈 | [学习模板](templates/learning-template.md) |
| Knowledge Management | 区分来源、理解与应用 | [知识模板](templates/knowledge-template.md) |
| Reflection System | 整理事件、感受与可检验解释 | [反思模板](templates/reflection-template.md) |
| AI Agent Workflow | 按任务读取最少上下文，保留证据边界 | [Agent 规则](AGENTS.md) |
| Prompt Management | 按输入、输出、约束维护提示词 | [提示词目录](prompts/README.md) |
| Weekly Review | 比较计划、执行与结果，确定下周重点 | [周复盘模板](templates/review-template.md) |
| Habit Tracking | 记录触发条件、实际次数与调整 | [习惯模板](templates/habit-template.md) |

## 环境要求与安装

- Windows 10 或更新版本、Python 3.10 或更新版本。应用只依赖 Python 标准库，不需要安装 npm 或第三方 Python 包。
- 可选：使用 AI 分析时，需要安装本机 Ollama 和适合设备的本地模型；普通记录功能不需要它。

从本仓库下载 ZIP 并解压，或使用 `git clone` 下载项目。在项目根目录打开 PowerShell 或 CMD，然后按下节启动。无需运行依赖安装命令。

## 启动方式

在项目目录双击 `Start-PGOS.cmd`，或从 CMD 运行 `Start-PGOS.cmd`。也可以在 PowerShell 中运行：

```powershell
.\Start-PGOS.ps1
```

脚本查找 Python 3.10+，优先打开 Edge 独立应用窗口；无 Edge 时使用默认浏览器。如果系统阻止脚本，仅对本次进程运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-PGOS.ps1`。

也可直接运行 `python -B -m app.server`。工具只使用 Python 标准库，无需 npm 或第三方 Python 包。初次体验可运行 `.\Start-PGOS.ps1 -Demo`，演示使用临时虚构数据，退出服务时清理。

App 提供六类记录、最近时间线、标题/日期筛选、全文关键词搜索、Markdown 编辑、反思字段引导、回收站删除与恢复，以及可选本地 AI 草稿。点击「保存」或 Ctrl+S 后写入 `private/workspace/`；不会自动更新长期模型。完整说明与限制见 [App 使用指南](docs/app-v1.md)。

## Ollama 使用说明（可选）

1. 从 [Ollama 官方网站](https://ollama.com) 的 [Windows 下载页](https://ollama.com/download/windows) 下载安装程序，完成安装并启动 Ollama。
2. 在终端下载本地模型，例如 `ollama pull gemma4:e2b`。模型文件约 7.2 GB；请根据设备内存和磁盘空间选择模型。可用 `ollama list` 查看已安装模型。
3. 本项目固定连接本机 `127.0.0.1:11434` 的 Ollama 服务，不需要填写 API 密钥或配置远程地址。若服务未运行，可先退出已有 Ollama 进程，在单独的 PowerShell 窗口中执行以下命令，再启动本项目：

   ```powershell
   $env:OLLAMA_NO_CLOUD = '1'
   ollama serve
   ```

4. 在应用中选择 1–5 条记录，点击「本地 AI 分析」，核对输入范围，检测并选择本地模型，再点击生成。可选填自定义分析提示词；草稿只会在你确认后保存。

项目只接受本机安装的非云端模型。Ollama 的安装、模型下载与本地 API 用法以[官方快速上手文档](https://docs.ollama.com/quickstart)为准。

继续使用原有文件工作流：

```sh
python scripts/pgos.py init
python scripts/pgos.py check
```

初始化会创建 `private/workspace/` 下的八类起始记录及 `private/config.yaml`，已有文件不会被覆盖。检查命令只扫描公开清单，不会读取私人日记。也可以手动复制 `templates/` 到 `private/workspace/` 使用。

1. 在 `private/workspace/goals/current.md` 中写一个目标及其可检查产出。
2. 在学习记录中填写一次实际练习，给出产出和卡点。
3. 使用 [周复盘提示词](prompts/weekly-review.md)，仅提供本周必要记录。
4. 把复盘写入 `private/workspace/reflections/`，保留建议与已执行行动的区别。

完整操作见 [上手指南](docs/getting-started.md) 和 [工作流](docs/workflow.md)。所有示例均为重新编写的虚构场景。

## 配置

[配置示例](config/config.example.yaml) 是给使用者与 Agent 阅读的约定。初始化工具仅复制它，当前不解析 YAML，也不按配置连接模型服务。按需修改本地 `private/config.yaml`；凭证只通过外部工具支持的环境变量提供。

## 项目结构

```text
AGENTS.md             Agent 入口与读取边界
docs/                 架构、使用方法、隐私与发布流程
rules/                归档、分析、证据、存储和 Git 规则
prompts/              可复用提示词
templates/            空白记录与个人记忆模板
examples/             明确标注的虚构用户数据
config/               公开配置示例和精确导出清单
scripts/              本地初始化、检查与导出工具
app/                  Python 数据与 HTTP 服务、离线网页界面
Start-PGOS.ps1        Windows 启动入口
Start-PGOS.cmd        CMD 与双击启动入口
tests/                隐私边界和文件操作回归测试
private/              本地数据、配置及备份；禁止公开
```

## 隐私与发布

真实姓名、学校、个人定位、联系方式、目标详情、私人日记、职业规划、Agent 私人记忆、凭证和本机路径均不得放入公开文件。不要直接把真实记录改名为 example；示例必须重新编写。

`.gitignore` 不是加密，也不会清除已跟踪文件和旧提交。AI 服务可能接收你提供的内容；只提交本次任务必需且你愿意分享的材料。

```sh
python scripts/pgos.py check
python scripts/pgos.py export
```

导出到 `private/release/personal-growth-os/`，仅复制清单内文件，不包含 `.git`、私有数据、旧提交或扫描日志。目标已存在时拒绝覆盖。发布前人工检查导出内容；从曾记录私人资料的仓库迁移时，应在仓库外使用该导出建立全新历史，不能推送原仓库来替代导出。

扫描是启发式检查，不能保证识别所有姓名、隐含身份或未见过的凭证格式。详见 [隐私边界](docs/privacy.md) 与 [发布清单](docs/release-checklist.md)。

App 只监听回环地址，关闭普通浏览器窗口不会自动停止服务；请使用应用「退出」按钮或启动终端中的 Ctrl+C。不要向局域网或公网转发此服务。

贡献方式见 [CONTRIBUTING](CONTRIBUTING.md)，版本记录见 [CHANGELOG](CHANGELOG.md)。项目采用 [MIT License](LICENSE)。

## Credits / Acknowledgements

本项目的本地记录应用在交互设计上参考了 [Pile](https://github.com/UdaraJay/Pile)，作者为 [Udara Jay](https://github.com/UdaraJay)。具体参考包括按类型浏览记录的侧栏、按日期组织记录的方式，以及独立的写作区域。本项目使用自己的 Python 标准库服务、网页界面和 Markdown 数据流程；未复制 Pile 的代码、图标、品牌素材或资源，也不属于 Pile 项目或与其作者存在官方关联。

Pile 的[代码许可证](https://github.com/UdaraJay/Pile/blob/main/LICENSE.md)为 MIT License，版权声明为 Copyright (c) 2023-present Udara Jay；其名称、标志和其他品牌元素不在 MIT 授权范围内。若将来实际引入 Pile 代码，须在分发时保留其版权声明和许可证文本，并单独检查相关素材的使用许可。
