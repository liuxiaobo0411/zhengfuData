# zhengfudata

建筑资质公开信息监测与归档系统的正式应用代码仓库。

系统用于抓取国家及地方政府公开网站中的建筑资质相关公告、政府文件、行政许可、企业名单、考试人员公告等信息，保存正文和附件，识别新增和变化，并通过 OpenClaw 推送企微通知。

## 当前状态

截至 2026-06-28，V1 MVP 和 V2 轻量本地知识库 MVP 已完成本机闭环开发与自动验收：本地 `zhengfudata doctor` 为 `ok=9 warn=0 fail=0`，最新 GitHub CI 已通过 Ubuntu / Windows Python 3.11 / 3.12 测试矩阵，并分别执行 Windows 与 Ubuntu 轻量本机验收脚本。当前剩余外部验收重点是目标 Windows 电脑实机安装运行、更多政府网站适配，以及后续 OpenClaw 入站问答和资质报告生成增强。

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
- `browser_rendered` 基础渲染抓取策略，按需安装 Playwright 后可用于动态页面。
- JSON API 列表抓取服务。
- 详情页正文解析、附件链接识别、附件下载。
- 页面 HTML / JSON 快照保存。
- 公告去重入库与新增公告、附件新增、抓取失败 change log。
- 后台栏目列表支持手动触发单栏目抓取。

当前已根据 Excel 配置首批真实来源：

- 住房和城乡建设部：政策发布、行政规范性文件库、建设工程企业资质行政审批专栏下的部门规章、资质标准、政策文件、审查意见公示、公告、通报、工程审批改革政策文件。
- 陕西省住房和城乡建设厅：公告公示、省厅文件。
- 陕西省工程建设企业资质公告接口：陕西建筑施工公告、陕西资质查询、陕西资质增项公告查询。
- 陕西资质增项公告查询页面已通过公开 JSON 接口接入，避免依赖动态页面渲染。

M3 已进入第一轮实现：

- 重复抓取同一批数据不会重复新增公告或附件。
- 正文 hash 变化会写入 `content_changed`。
- 附件文件 hash 变化会写入 `attachment_changed`。
- 附件下载失败会写入 `attachment_failed`。
- 列表和正文抓取成功但附件失败时，抓取任务状态会标记为 `partial_success`。
- 抓取批次会统计新增公告、正文变化、附件新增、附件变化、附件成功和附件失败数量。
- 附件下载会尽量保存 HTTP `Last-Modified` 作为文件更新时间。
- 附件首次成功下载和内容变化时会写入 `attachment_versions`，保留版本号、hash、本地路径和变化类型。
- `http_with_retry` 会按栏目请求间隔做递增等待，避免失败时高频重试。

M4 已进入第一轮实现：

- 后台可查看公告列表和公告详情。
- 后台可查看全局变化记录，按变化类型、网站和栏目筛选。
- 后台可查看附件列表，按关键词、状态、网站和本地文件筛选，并通过下载接口下载本地附件。
- 后台附件管理页可将当前筛选下已保存的本地附件打包为 ZIP 下载。
- 后台附件管理页展示附件版本数量，公告详情展示最近附件版本 hash 和本地相对路径。
- 后台附件列表和公告详情可打开原始附件地址，并可手动重试失败附件下载。
- 后台可查看抓取任务列表和任务详情，任务详情可展示关联通知状态。
- 工作台展示真实运行统计、今日新增/变化/失败和最近变化流。
- 后台只展示相对路径和下载入口，不暴露本机绝对路径。

M5 已进入第一轮实现：

- 可生成抓取日报 payload 和 markdown 文本。
- 可通过 `OPENCLAW_WEBHOOK_URL` POST 到 OpenClaw。
- 通知成功、失败和未配置原因会写入 `notification_logs`。
- 后台可查看通知日志。
- 通知发送失败会按 `OPENCLAW_NOTIFY_RETRY_TIMES` 自动重试，后台也可手动重试通知。

M6 已开始推进：

- 已接入应用内部 APScheduler 每日定时任务。
- 可通过 CLI 手动运行一次每日抓取闭环。
- 可在后台工作台和抓取任务页手动触发一次每日抓取。
- 可在后台网站栏目页手动触发单网站抓取，系统会抓取该网站下启用栏目。
- 后台新增和编辑网站、栏目时提供服务端基础校验，避免错误 URL、重复标识和非法请求头配置入库。
- 后台网站栏目页支持“测试抓取”，可在不入库、不通知的情况下验证栏目列表是否可访问和可解析。
- 每日任务会按启用网站和启用栏目抓取，并在结束后发送日报。
- 同一栏目已有运行中任务时不会重复启动抓取；应用启动时会清理超时的 running 任务。
- `configs/sites.yaml` 已包含 14 个启用栏目。
- 已补充 Windows 本地部署脚本和任务计划脚本。
- 可通过 `zhengfudata validate-sources` 验证启用栏目列表页是否可访问和可解析。
- 后台已提供只读系统配置页，查看运行环境、storage、调度、OpenClaw、Windows 脚本和 macOS/Linux 脚本状态。
- 可通过 `zhengfudata export-acceptance-report` 导出 V1 自动验收报告，包含部署自检摘要、后台入口、失败来源和处理建议。
- 可通过 `zhengfudata doctor` 做部署自检，检查数据库核心表、默认密码和密钥、storage、来源配置、OpenClaw、Windows 脚本和 macOS/Linux 脚本状态。
- 可通过 `zhengfudata acceptance-check` 一键执行部署自检、来源抽样验证和验收报告导出。
- 可通过 `zhengfudata local-acceptance-check` 跨平台执行本机交付验收，串联部署自检、来源抽样、每日抓取抽样、V2 验收和验收报告导出。

已有设计文档位于 `docs/` 目录：

- [V1 MVP 详细设计](./docs/建筑资质公开信息监测与归档系统_V1_MVP详细设计.md)
- [V2 详细设计](./docs/建筑资质公开信息监测与归档系统_V2_详细设计.md)
- [前端 UI 详细设计](./docs/建筑资质公开信息监测与归档系统_前端UI详细设计.md)
- [UI 视觉哲学](./docs/建筑资质公开信息监测与归档系统_UI视觉哲学.md)
- [V1 MVP 验收记录](./docs/V1_MVP验收记录.md)
- [V2 验收验证记录](./docs/V2_验收验证记录.md)
- [Windows 本地部署说明](./docs/Windows本地部署说明.md)
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
APP_RUNNING_RUN_TIMEOUT_MINUTES=360

ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me

OPENCLAW_DASHBOARD_URL=http://127.0.0.1:18789/
OPENCLAW_NOTIFY_MODE=webhook
OPENCLAW_CLI_COMMAND=openclaw
OPENCLAW_WEBHOOK_URL=
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_NOTIFY_RETRY_TIMES=2
WECOM_NOTIFY_TARGET_TYPE=direct
WECOM_NOTIFY_TARGET_ID=
CRAWLER_ATTACHMENT_TIMEOUT_SECONDS=10
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

执行本机交付验收：

```bash
scripts/run-local-acceptance.sh --source-limit 2 --daily-limit 2
```

如需启用 `browser_rendered` 动态页面策略，额外安装：

```bash
python -m pip install -e ".[browser]"
python -m playwright install chromium
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
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
scripts\windows\setup.ps1
scripts\windows\run-server.ps1
```

运行每日抓取：

```powershell
scripts\windows\run-daily-crawl.ps1 -Limit 2
```

完整说明见 [Windows 本地部署说明](./docs/Windows本地部署说明.md)。

## 开发验证

提交前至少运行：

```bash
ruff check .
ruff format --check .
pytest
```

GitHub 已配置 CI，推送到 `main` 或创建 PR 时会在 Ubuntu / Windows 的 Python 3.11 和 3.12 上自动运行同一组质量门，并分别在 Windows 和 Ubuntu 上执行本机验收脚本轻量模式。

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

验证启用栏目是否可访问并解析到列表记录：

```bash
zhengfudata validate-sources
```

运行本地部署自检：

```bash
zhengfudata doctor
```

只验证前 2 个启用栏目：

```bash
zhengfudata validate-sources --limit 2
```

导出 V1 自动验收报告：

```bash
zhengfudata export-acceptance-report
```

一键执行本地验收检查：

```bash
zhengfudata acceptance-check --source-limit 2
```

执行跨平台本机交付验收：

```bash
zhengfudata local-acceptance-check --source-limit 2 --daily-limit 2
```

macOS / Linux 也可以使用脚本封装：

```bash
scripts/run-local-acceptance.sh --source-limit 2 --daily-limit 2
```

只验证部署、配置和报告导出时，可跳过依赖外部网站或 V2 数据的步骤：

```bash
zhengfudata local-acceptance-check --skip-source-validation --skip-daily-crawl --skip-v2
```

解析已下载附件并构建本地知识库：

```bash
zhengfudata parse-attachments --limit 20
zhengfudata rebuild-search-index
```

执行知识库关键词检索和问答摘要：

```bash
zhengfudata kb-search "建筑业企业资质延续"
zhengfudata kb-ask "最近建筑业企业资质延续公告有哪些？"
```

`kb-search` 支持按类型、来源网站和发布时间范围筛选：

```bash
zhengfudata kb-search "资质延续" --entity-type attachment --site-name "陕西省住房和城乡建设厅" --published-from 2026-06-23 --published-to 2026-06-25
```

一键执行 V2 知识库验收检查：

```bash
zhengfudata v2-acceptance-check
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

如果 OpenClaw 已通过本机 CLI 接入企业微信，可改用 CLI 通知模式：

```env
OPENCLAW_NOTIFY_MODE=cli
OPENCLAW_CLI_COMMAND=openclaw
WECOM_NOTIFY_TARGET_ID=企微群chatid
```

当前 OpenClaw CLI 企业微信通道发送群消息时使用裸 `chatid`；如果误填
`group:` 或 `chat:` 前缀，应用会在调用 CLI 前自动剥离前缀。

运行一次“每日抓取 + 日报通知”完整闭环：

```bash
zhengfudata run-daily-crawl
```

默认情况下，完整每日抓取会在抓取完成后按 `KB_PARSE_BATCH_LIMIT` 自动解析一批已下载附件，
让新附件内容尽快进入本地知识库。若只想抓取和通知，不自动解析附件，可在 `.env` 中设置：

```env
KB_ENABLE_ATTACHMENT_PARSE=false
```

只抓取前 2 个启用栏目并发送日报：

```bash
zhengfudata run-daily-crawl --limit 2
```

只抓取不发送日报：

```bash
zhengfudata run-daily-crawl --no-notify
```

也可以登录后台，在“工作台”或“抓取任务”页面点击“执行每日抓取”。“抓取任务”页面可勾选“发送日报”同步触发 OpenClaw 通知。

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
- 可先测试抓取单个栏目，确认来源可访问和可解析后再正式启用。
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
