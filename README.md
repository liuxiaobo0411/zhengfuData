# zhengfudata

建筑资质公开信息监测与归档系统的正式应用代码仓库。

系统用于抓取国家及地方政府公开网站中的建筑资质相关公告、政府文件、行政许可、企业名单、考试人员公告等信息，保存正文和附件，识别新增和变化，并通过 OpenClaw 推送企微通知。

## 当前状态

当前已进入正式开发，M0-M6 已完成第一轮核心闭环实现，后续重点是端到端验收、Windows 运行验证和更多站点适配。

M0 项目底座已具备：

- FastAPI 应用入口、健康检查接口和基础后台工作台页面。
- `.env` + `configs/app.yaml` 配置体系。
- SQLite / SQLAlchemy / Alembic 基础配置。
- 本地 `storage/` 目录初始化。
- Windows 兼容的附件文件名清洗工具。
- pytest 与 ruff 开发质量检查。

M1 已完成第一版：

- 核心业务表迁移：`users`、`sites`、`site_sections`、`crawl_runs`、`announcements`、`attachments`、`change_logs`。
- 简单账号密码登录。
- 政府网站新增、编辑、启用、停用。
- 栏目新增、编辑、启用、停用。
- 栏目抓取策略、请求参数、解析选择器等配置字段。

M2 已进入第一轮实现：

- 静态 HTML 列表页抓取服务。
- JSON API 列表抓取服务。
- 详情页正文解析、附件链接识别、附件下载。
- 页面 HTML / JSON 快照保存。
- 公告去重入库与新增公告、附件新增、抓取失败 change log。
- 后台栏目列表支持手动触发单栏目抓取。

当前已根据 Excel 配置首批真实来源：

- 住房和城乡建设部：政策发布、行政规范性文件库、建设工程企业资质行政审批专栏下的部门规章、资质标准、政策文件、审查意见公示、公告、通报、工程审批改革政策文件。
- 陕西省住房和城乡建设厅：公告公示、省厅文件。
- 陕西省工程建设企业资质公告接口：陕西建筑施工公告。
- 陕西资质查询、陕西资质增项公告查询页面已保留为 `browser_rendered` 待适配项，默认不启用。

M3 已进入第一轮实现：

- 重复抓取同一批数据不会重复新增公告或附件。
- 正文 hash 变化会写入 `content_changed`。
- 附件文件 hash 变化会写入 `attachment_changed`。
- 附件下载失败会写入 `attachment_failed`。
- 抓取批次会统计新增公告、正文变化、附件新增、附件变化、附件成功和附件失败数量。

M4 已进入第一轮实现：

- 后台可查看公告列表和公告详情。
- 后台可查看附件列表，并通过下载接口下载本地附件。
- 后台可查看抓取任务列表和任务详情。
- 后台只展示相对路径和下载入口，不暴露本机绝对路径。

M5 已进入第一轮实现：

- 可生成抓取日报 payload 和 markdown 文本。
- 可通过 `OPENCLAW_WEBHOOK_URL` POST 到 OpenClaw。
- 通知成功、失败和未配置原因会写入 `notification_logs`。
- 后台可查看通知日志。

M6 已开始推进：

- 已接入应用内部 APScheduler 每日定时任务。
- 可通过 CLI 手动运行一次每日抓取闭环。
- 每日任务会按启用网站和启用栏目抓取，并在结束后发送日报。
- `configs/sites.yaml` 已包含 12 个启用栏目和 2 个待适配查询页面。

已有设计文档位于 `docs/` 目录：

- [V1 MVP 详细设计](./docs/建筑资质公开信息监测与归档系统_V1_MVP详细设计.md)
- [前端 UI 详细设计](./docs/建筑资质公开信息监测与归档系统_前端UI详细设计.md)
- [UI 视觉哲学](./docs/建筑资质公开信息监测与归档系统_UI视觉哲学.md)
- [V1 MVP 验收记录](./docs/V1_MVP验收记录.md)
- [工作台 Demo PNG](./docs/assets/建筑资质公开信息监测与归档系统_工作台Demo.png)

原型脚本位于上一级目录：

- `../june_archive.py`

原型脚本只用于验证，不作为正式架构直接继续堆功能。

## 同事快速接手

新同事接手时建议按这个顺序看：

1. 先读 `docs/建筑资质公开信息监测与归档系统_V1_MVP详细设计.md`，确认业务边界。
2. 再读 `CONTRIBUTING.md`，确认开发规范、提交要求和完成定义。
3. 按本文“开发启动流程”启动本地服务。
4. 跑一次 `pytest`、`ruff check .`、`ruff format --check .`，确认本地环境干净。
5. 从 `configs/sites.yaml` 导入站点，使用 `zhengfudata crawl-enabled --limit 2` 做最小抓取验证。

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

## 项目结构

```text
app/
  main.py
  config.py
  database.py
  models/
  services/
    crawler/
    notifier/
    storage.py
    site_importer.py
    path_utils.py
  routers/
    web/
    api/
  templates/
  static/
configs/
  app.yaml
data/
  app.db
storage/
  attachments/
  snapshots/
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
APP_CONFIG_FILE=configs/app.yaml
APP_PUBLIC_BASE_URL=http://127.0.0.1:8000
APP_SCHEDULER_ENABLED=false
APP_SCHEDULER_DAILY_TIME=09:00
APP_TIMEZONE=Asia/Shanghai

ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me

OPENCLAW_DASHBOARD_URL=http://127.0.0.1:18789/
OPENCLAW_WEBHOOK_URL=
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
WECOM_NOTIFY_TARGET_TYPE=direct
WECOM_NOTIFY_TARGET_ID=
```

不要提交真实密码、OpenClaw token、企微 secret、客户路径或客户数据。

## 开发启动流程

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

启动后访问：

- 后台工作台：http://127.0.0.1:8000/
- 健康检查：http://127.0.0.1:8000/api/health

默认登录账号来自 `.env`：

```text
admin / change-me
```

正式使用前必须修改 `ADMIN_PASSWORD` 和 `APP_SECRET_KEY`。

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

如 Windows 当前 PowerShell 禁止执行虚拟环境脚本，可先在当前窗口执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 开发验证

提交前至少运行：

```bash
ruff check .
ruff format --check .
pytest
```

涉及数据库结构变更时，还需要运行：

```bash
alembic upgrade head
```

涉及后台页面时，需要本地打开页面人工检查一次，至少确认登录、导航、列表、详情、下载入口和错误提示可用。

## 首批站点导入与抓取

导入 `configs/sites.yaml` 中的首批真实站点：

```bash
zhengfudata import-sites --file configs/sites.yaml
```

手动抓取全部启用栏目：

```bash
zhengfudata crawl-enabled
```

只抓取前 2 个启用栏目用于快速验证：

```bash
zhengfudata crawl-enabled --limit 2
```

抓取单个栏目：

```bash
zhengfudata crawl-section 1
```

发送当天抓取日报到 OpenClaw：

```bash
zhengfudata send-daily-report
```

运行一次“每日抓取 + 日报通知”完整闭环：

```bash
zhengfudata run-daily-crawl
```

只抓取前 2 个启用栏目并发送日报：

```bash
zhengfudata run-daily-crawl --limit 2
```

只抓取不发送日报：

```bash
zhengfudata run-daily-crawl --no-notify
```

启用应用内部每日定时任务时，在 `.env` 中配置：

```env
APP_SCHEDULER_ENABLED=true
APP_SCHEDULER_DAILY_TIME=09:00
APP_TIMEZONE=Asia/Shanghai
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
