# zhengfudata

建筑资质公开信息监测与归档系统的正式应用代码仓库。

系统用于抓取国家及地方政府公开网站中的建筑资质相关公告、政府文件、行政许可、企业名单、考试人员公告等信息，保存正文和附件，识别新增和变化，并通过 OpenClaw 推送企微通知。

## 开发状态

当前处于 M0 项目底座搭建前。此目录是空 git 仓库，后续正式应用代码从这里开始提交。

已有设计文档位于上一级目录：

- `../建筑资质公开信息监测与归档系统_V1_MVP详细设计.md`
- `../建筑资质公开信息监测与归档系统_前端UI详细设计.md`
- `../建筑资质公开信息监测与归档系统_UI视觉哲学.md`

原型脚本位于上一级目录：

- `../june_archive.py`

原型脚本只用于验证，不作为正式架构直接继续堆功能。

## V1 技术栈

- Python 3.11+
- FastAPI
- Jinja2 + Bootstrap
- SQLite
- SQLAlchemy + Alembic
- APScheduler
- httpx + BeautifulSoup
- Playwright 按需启用
- OpenClaw 企微通知

## 目标项目结构

```text
app/
  main.py
  config.py
  database.py
  models/
  schemas/
  services/
    crawler/
    parser/
    detector/
    downloader/
    notifier/
    scheduler/
  adapters/
  routers/
    web/
    api/
  templates/
  static/
configs/
  sites.yaml
data/
  app.db
storage/
  attachments/
  snapshots/
  exports/
  logs/
tests/
```

## 本地开发原则

所有路径必须可配置，不允许硬编码某台电脑的绝对路径。默认目录可以是：

```text
data/
storage/
logs/
```

生产或客户机器上通过 `.env` 或 `config.yaml` 覆盖。

## 配置项建议

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
APP_SECRET_KEY=change-me
APP_DATABASE_URL=sqlite:///data/app.db
APP_STORAGE_ROOT=storage

ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me

OPENCLAW_DASHBOARD_URL=http://127.0.0.1:18789/
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
WECOM_NOTIFY_TARGET_TYPE=direct
WECOM_NOTIFY_TARGET_ID=
```

不要提交真实密码、OpenClaw token、企微 secret、客户路径或客户数据。

## 开发启动流程

M0 完成后，本节应补充真实命令。目标形式如下：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Windows 环境应提供等价命令：

```powershell
py -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## 开发顺序

按设计文档的 M0 到 M6 顺序推进：

1. M0 项目底座与开发规范。
2. M1 数据模型与基础后台。
3. M2 抓取核心闭环。
4. M3 变化检测与任务统计。
5. M4 后台查询与本地归档体验。
6. M5 OpenClaw 企微通知。
7. M6 扩展站点与端到端验收。

不要跳过 M0/M1 直接堆抓取逻辑。

## 当前验收标准

V1 MVP 完成后至少满足：

- 可维护政府网站和栏目。
- 可配置抓取策略。
- 可手动和定时抓取。
- 可抓取至少 10 个网站或栏目。
- 可保存正文、附件、原始地址、本地快照和 hash。
- 可识别新增公告、正文变化、附件新增和附件变化。
- 可查看任务成功、失败、部分成功状态。
- 可查看失败地址和失败原因。
- 可通过 OpenClaw 向企微发送日报。
- 可在 Windows 本地运行。

详细验收以设计文档为准。

## 协作规范

请阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)。
