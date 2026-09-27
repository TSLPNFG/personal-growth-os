# Windows 启动入口

## 双击启动

在项目文件夹中双击 `Start-PGOS.cmd`。它会调用同目录的 PowerShell 启动器，自动查找 Python 并打开应用窗口。

不要双击 `Start-PGOS.ps1`：Windows 可能将它作为文本打开，而不是执行。

启动期间保留终端窗口；使用应用的「退出应用」按钮或在终端按 Ctrl+C 停止服务。若启动失败，窗口会保留错误信息，按任意键后关闭。

## CMD 启动

在项目文件夹的地址栏输入 `cmd` 并回车，再执行：

```bat
Start-PGOS.cmd
```

已有 CMD 窗口时，也可以用带引号的完整文件名调用启动器。启动器会定位自身所在目录，不要求调用者的当前目录恰好是项目目录。

参数示例：

```bat
Start-PGOS.cmd -Demo
Start-PGOS.cmd -Demo -NoBrowser -Port 8765
```

Demo 使用隔离的虚构数据；NoBrowser 只启动服务，手动打开终端显示的本机地址。Port 省略时自动选择可用端口。

## PowerShell 启动

```powershell
.\Start-PGOS.cmd
```

也可继续使用原有 `.\Start-PGOS.ps1`。CMD 入口只为这一次 PowerShell 子进程指定执行策略，不修改系统的持久执行策略。

## 验证步骤

1. CMD 中执行 `Start-PGOS.cmd -Demo -NoBrowser`，应显示本机服务地址和 DEMO 提示。
2. 打开显示的地址，确认页面标注「演示空间」，然后使用「退出应用」结束服务。
3. 双击 `Start-PGOS.cmd`，应打开普通工作空间的应用窗口；启动器本身不创建或修改记录。
4. 如果只打开了脚本文本，检查实际点击的是 `.cmd` 而不是 `.ps1`。
5. 如果找不到 Python，安装 Python 3.10+，或将 PGOS_PYTHON 指向已有解释器后重试。错误窗口会保留，不会立即消失。

此入口不包含应用业务逻辑；记录、删除、恢复和 AI 流程均由已有应用代码处理。
