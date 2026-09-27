# App V1 验证记录

本记录只包含虚构测试及技术结果，不包含真实使用者资料。

## 已验证

- Windows 上通过 Start-PGOS.ps1 启动隔离 Demo 的本地 HTTP 服务。
- 自动化测试：29 项用例，28 项通过、1 项因 Windows 符号链接权限跳过。目录联接与硬链接边界用例均实际通过。
- 浏览器界面：打开六类入口与最近记录；从模板创建反思；填写事件、自述事实、感受、待验证解释、反例和下一步；保存后刷新页面并重开，内容仍存在。
- 浏览器界面：正文关键词搜索、日期筛选、标题排序、重命名并保存；确认 AI 输入范围只包含所选的一条记录。
- 浏览器界面：本机 Ollama 不可用时显示错误，普通编辑与保存继续正常使用。
- 自动化：AI 生成前后的文件快照相同；未确认拒绝落盘，确认后写入独立反思草稿，不修改源记录与长期模型。
- 自动化：拦截越界路径、链接、跨站请求、缺少会话值的 API 请求、云端模型和 HTTP 重定向；外部编辑冲突及原子写入失败不覆盖原文件。
- JavaScript 语法检查、公开内容扫描、相对文档链接与 Git 空白检查。
- 临时工程中实际执行公开导出：56 个清单文件包含 App 源码，无 private、Git 历史或临时记录。

## 未验证或不包含

- 真实 Ollama 模型推理未验证：当前本机服务不可用，成功响应与确认保存通过独立虚构替身测试，不代表真实模型效果。
- Edge 独立应用窗口未单独做原生桌面验收；实际 UI 验收在浏览器中完成。
- 不包含 Windows 安装包、签名、自动更新、托盘和跨设备同步。
- 未进行大型资料库性能压测、安全渗透审计或异常断电恢复测试。

以上早期验收使用临时目录，未读取私人历史，也未把虚构验收记录写入项目实际工作空间。

## 2026-09-27 公开候选复核

- 从精确清单导出 58 个公共文件；独立候选目录不含 private 或旧 Git 历史，文件数量与哈希核对通过。
- 在导出候选中执行 31 项自动测试：30 项通过，1 项因系统符号链接权限跳过；公开文件扫描为 0 项发现。
- 在导出候选中通过 `Start-PGOS.cmd -Demo -NoBrowser -Port 0` 启动服务；主页 HTTP 200、`/api/info` 确认 Demo 模式、退出接口 HTTP 200、进程退出码 0。
- 真实 Ollama 模型生成及资源管理器实际双击仍未在本次复核中验证。

## 本轮文件清单

新增：

- Start-PGOS.ps1
- app/__init__.py
- app/storage.py
- app/ai.py
- app/server.py
- app/ui/index.html
- app/ui/styles.css
- app/ui/app.js
- tests/test_app.py
- docs/app-v1.md
- docs/app-validation.md

修改：

- scripts/pgos.py：允许经过清单审核的 HTML、CSS、JavaScript 与 PowerShell 文本源码导出。
- config/public-files.json：加入新公共源码和文档；移除已不存在的 CI 文件条目，不恢复用户删除的文件。
- README.md：本地 App 功能与启动说明。
- docs/architecture.md：方案比较、分层、Markdown 兼容与 AI 草稿流程。
- docs/privacy.md：本地 HTTP、文件和 AI 边界。
- docs/getting-started.md：新增图形界面入口。
- CHANGELOG.md：首版 App 变更记录。

AGENTS、现有规则和 Markdown 模板未改动。Pile 只用于只读参考。
