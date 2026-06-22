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
OPENCLAW_WEBHOOK_URL=OpenClaw 提供的通知地址
OPENCLAW_NOTIFY_RETRY_TIMES=2
```

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
- `scripts\windows\doctor.ps1` 无 `FAIL`。
- `scripts\windows\acceptance-check.ps1 -SourceLimit 2` 成功。
- `scripts\windows\validate-sources.ps1 -Limit 2` 成功。
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
