# Windows 本地部署说明

本文用于把建筑资质公开信息监测与归档系统部署到一台独立 Windows 电脑上运行。

## 运行条件

- Windows 10 / Windows 11。
- Python 3.11 或 3.12。
- PowerShell。
- 可以访问目标政府网站和 OpenClaw 服务。

建议先安装 Python，并确认命令可用：

```powershell
py --version
```

如果机器没有 `py` 启动器，也可以使用：

```powershell
python --version
```

## 初始化

在项目根目录执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
scripts\windows\setup.ps1
```

如果机器使用的是 `python` 命令：

```powershell
scripts\windows\setup.ps1 -PythonCommand python
```

初始化脚本会完成：

- 创建 `.venv` 虚拟环境。
- 安装项目和开发依赖。
- 如果不存在 `.env`，从 `.env.example` 创建。
- 执行数据库迁移。
- 导入 `configs/sites.yaml` 中的首批站点配置。

如需启用 `browser_rendered` 动态页面策略，需要额外安装 Playwright：

```powershell
.venv\Scripts\python.exe -m pip install -e ".[browser]"
.venv\Scripts\python.exe -m playwright install chromium
```

初始化后必须修改 `.env`：

```env
APP_SECRET_KEY=请改成随机长字符串
ADMIN_PASSWORD=请改成强密码
APP_PUBLIC_BASE_URL=http://127.0.0.1:8000
OPENCLAW_NOTIFY_MODE=webhook
OPENCLAW_CLI_COMMAND=openclaw
OPENCLAW_WEBHOOK_URL=OpenClaw 提供的通知地址
OPENCLAW_NOTIFY_RETRY_TIMES=2
APP_RUNNING_RUN_TIMEOUT_MINUTES=360
```

如果 Windows 机器上已安装并配置 OpenClaw CLI 企业微信通道，也可以使用 CLI 通知模式：

```env
OPENCLAW_NOTIFY_MODE=cli
OPENCLAW_CLI_COMMAND=openclaw
WECOM_NOTIFY_TARGET_ID=企微群chatid
```

OpenClaw CLI 企业微信通道发送群消息时使用裸 `chatid`；如果误填 `group:` 或
`chat:` 前缀，应用会在调用 CLI 前自动剥离前缀。

## 从开发机导出部署包

如果要把当前项目复制到另一台 Windows 电脑上运行，建议先在开发机或已有项目目录导出干净部署包：

```powershell
scripts\windows\export-deployment-package.ps1
```

也可以指定输出目录或 zip 文件：

```powershell
scripts\windows\export-deployment-package.ps1 -Output exports
scripts\windows\export-deployment-package.ps1 -Output exports\zhengfudata_windows.zip
```

导出后可在当前机器先模拟目标电脑解压安装验收：

```powershell
scripts\windows\verify-deployment-package.ps1 -PackagePath exports\zhengfudata_windows.zip -PythonCommand python
```

该命令会把 zip 解压到临时目录，确认包内没有 `.env`、`data`、`storage`、`.venv`、`.git` 等本机状态，然后在解压目录运行初始化、自检和轻量本机验收。

项目推送到 GitHub 后，CI 会在 Windows runner 上执行同样的导出和解压安装验收。通过后可在对应 GitHub Actions 运行页面下载 `zhengfudata-windows-deployment` artifact，里面包含已验证的 `ci_windows_deployment.zip`。

目标 Windows 电脑实机验收时，建议同步填写 `docs\Windows实机验收记录模板.md`，记录执行命令、报告路径、截图位置、问题和最终结论。

跨平台 CLI 等价命令：

```powershell
.venv\Scripts\python.exe -m app.cli export-deployment-package
```

部署包默认输出到：

```text
storage\exports\
```

部署包只包含应用代码、迁移、配置模板、站点配置、脚本和文档，不包含 `.env`、`data`、`storage`、`.venv`、`.git` 或本机缓存。复制到目标 Windows 电脑后，解压 zip，进入解压后的 `zhengfudata` 目录，再执行本文“初始化”和“运行部署自检”步骤。

## 运行部署自检

```powershell
scripts\windows\doctor.ps1
```

自检会检查数据库连接、核心表结构、默认密码和密钥、storage 写入、站点配置文件、已导入来源、OpenClaw 配置和 Windows 脚本完整性。`WARN` 表示可继续运行但需要关注，`FAIL` 表示需要先修复。

也可以直接运行一键验收检查：

```powershell
scripts\windows\acceptance-check.ps1 -SourceLimit 2
```

该脚本会依次执行部署自检、来源抽样验证，并导出 V1 验收报告。

验证 V2 知识库能力时运行：

```powershell
scripts\windows\v2-acceptance-check.ps1
```

该脚本会检查附件解析、知识库索引、后台/API 查询和 OpenClaw 问答入口是否可用。

如果要在 Windows 机器上一次性完成本机交付验收，可以运行：

```powershell
scripts\windows\run-local-acceptance.ps1 -SourceLimit 2 -DailyLimit 2
```

该脚本会依次执行部署自检、来源抽样验证、每日抓取抽样（不发送企微通知）、V2 知识库验收，并导出验收报告。只验证部署和配置时可跳过耗时步骤：

```powershell
scripts\windows\run-local-acceptance.ps1 -SkipSourceValidation -SkipDailyCrawl -SkipV2
```

该 PowerShell 脚本是跨平台 CLI 的 Windows 封装；同一流程也可以直接运行：

```powershell
.venv\Scripts\python.exe -m app.cli local-acceptance-check --source-limit 2 --daily-limit 2
```

## 验证来源配置

先验证前 2 个启用栏目：

```powershell
scripts\windows\validate-sources.ps1 -Limit 2
```

验证全部启用栏目：

```powershell
scripts\windows\validate-sources.ps1
```

这个命令只请求列表页并解析记录数，不会写入数据库，也不会下载附件。

## 启动后台

```powershell
scripts\windows\run-server.ps1
```

浏览器访问：

```text
http://127.0.0.1:8000/
```

默认账号来自 `.env`：

```text
admin / change-me
```

正式使用前不要保留默认密码。

## 手动运行每日抓取

只抓前 2 个启用栏目验证链路：

```powershell
scripts\windows\run-daily-crawl.ps1 -Limit 2
```

抓取全部启用栏目：

```powershell
scripts\windows\run-daily-crawl.ps1
```

只抓取，不发送通知：

```powershell
scripts\windows\run-daily-crawl.ps1 -NoNotify
```

如果验收报告或附件管理页出现失败附件，可以批量重试：

```powershell
scripts\windows\retry-failed-attachments.ps1 -Timeout 60
```

只重试前 5 个失败附件：

```powershell
scripts\windows\retry-failed-attachments.ps1 -Limit 5 -Timeout 60
```

## 导出验收报告

```powershell
scripts\windows\export-acceptance-report.ps1
```

报告默认输出到：

```text
storage\exports\
```

## 每日定时运行

方式一：应用内置调度。

在 `.env` 中启用：

```env
APP_SCHEDULER_ENABLED=true
APP_SCHEDULER_DAILY_TIME=09:00
APP_TIMEZONE=Asia/Shanghai
```

然后保持后台服务运行：

```powershell
scripts\windows\run-server.ps1
```

方式二：Windows 任务计划。

```powershell
scripts\windows\install-daily-task.ps1 -DailyTime 09:00
```

任务计划会每天调用：

```powershell
scripts\windows\run-daily-crawl.ps1
```

## 数据目录

默认目录：

```text
data\app.db
storage\attachments
storage\snapshots
```

这些目录不要提交到 Git。迁移到另一台电脑时，可以复制 `data` 和 `storage` 作为本地数据备份。

## 验收清单

在 Windows 机器上至少完成：

- `scripts\windows\setup.ps1` 成功。
- 如从开发机迁移，`scripts\windows\export-deployment-package.ps1` 可生成部署包，目标 Windows 电脑可正常解压。
- `scripts\windows\verify-deployment-package.ps1 -PackagePath <部署包.zip> -PythonCommand python` 可在临时目录完成解压安装验收。
- `scripts\windows\doctor.ps1` 无 `FAIL`。
- `scripts\windows\acceptance-check.ps1 -SourceLimit 2` 成功。
- `scripts\windows\run-local-acceptance.ps1 -SourceLimit 2 -DailyLimit 2` 成功。
- 填写 `docs\Windows实机验收记录模板.md`，记录命令输出、后台截图、验收报告路径和问题清单。
- `scripts\windows\v2-acceptance-check.ps1` 成功。
- `scripts\windows\validate-sources.ps1 -Limit 2` 成功。
- 如存在失败附件，`scripts\windows\retry-failed-attachments.ps1 -Timeout 60` 可恢复或输出失败原因。
- 后台可以登录。
- 后台网站栏目页可以对单个栏目执行“测试抓取”，并展示成功或失败原因。
- `scripts\windows\run-daily-crawl.ps1 -Limit 2` 成功。
- `scripts\windows\export-acceptance-report.ps1` 成功。
- 后台可以查看抓取任务、公告、附件和通知日志。
- 附件可以从后台下载。
- OpenClaw 配置后，企微群能收到日报。

## 常见问题

PowerShell 禁止执行脚本：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

端口被占用：

```powershell
scripts\windows\run-server.ps1 -Port 8010
```

需要重新导入站点：

```powershell
.venv\Scripts\python.exe -m app.cli import-sites --file configs/sites.yaml
```

需要重新验证来源：

```powershell
.venv\Scripts\python.exe -m app.cli validate-sources
```

需要导出验收报告：

```powershell
.venv\Scripts\python.exe -m app.cli export-acceptance-report
```

只想重跑数据库迁移：

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
```
