# 发布检查清单

- [ ] 在 private 外的公共文件中，没有真实个人记录或从其改名得到的示例。
- [ ] 阅读 config/public-files.json 的每一项，并人工检查内容和文件名。
- [ ] 运行 `python -B -m unittest discover -s tests`。
- [ ] 运行 `python -B scripts/pgos.py check`；有私有敏感词清单时加上 --denylist。
- [ ] 查看 `git status --short`、`git diff` 和 `git diff --cached`；注意这些本地输出可能显示旧私人数据，不可上传。
- [ ] 运行 `python -B scripts/pgos.py export`。若默认目标已存在，选择新的 private/release 子目录，禁止覆盖旧导出。
- [ ] 检查导出只包含清单文件，没有 .git、private 或附件。再次在导出目录运行检查及测试。
- [ ] 将导出复制到旧仓库之外的独立目录，确认它不处于其他 Git 仓库内。
- [ ] 选择新 GitHub 仓库及愿意公开的作者身份；不要直接把旧个人仓库改为公开。
- [ ] 完成人工隐私审核并明确授权后，才初始化新仓库、暂存清单文件、核对暂存差异并提交；推送需明确目标和授权。

工具不会执行 git add、commit 或 push。自动化检查不替代人工语义审阅，也不证明旧仓库或远端已清理。
