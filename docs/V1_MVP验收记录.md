# V1 MVP 验收记录

记录日期：2026-06-21

## 环境信息

- 操作系统：macOS 本地开发环境
- Python：项目虚拟环境 `.venv`
- 数据库：`sqlite:///data/app.db`
- 本地归档目录：`storage/`
- 站点配置：`configs/sites.yaml`

## 当前验收范围

本次验收聚焦首批 Excel 来源转配置，以及启用栏目列表页是否能被当前抓取器解析。

不包含：

- Windows 实机运行验收。
- 全量附件下载压力测试。
- 资质增项公告查询页面动态适配。
- 企微真实群日报发送。

## 首批来源配置

当前 `configs/sites.yaml` 已配置：

- 3 个站点。
- 14 个栏目。
- 13 个启用栏目。
- 1 个待适配动态查询页面，默认不启用。

待适配页面：

- 陕西资质增项公告查询页面：`https://qiye.sxxzsp.cn:29086/affiche`

已通过 JSON 接口接入：

- 陕西资质查询：`https://qiye.sxxzsp.cn:29086/api/portal/announcement/integration?fsystemid=101&pageSize=20&pageNum=1`

## 列表解析验证

执行命令：

```bash
zhengfudata import-sites --file configs/sites.yaml
```

结果：

```text
imported sites=3 sections=14
```

启用栏目列表探测结果：

```text
enabled_sections 13
OK 建设工程企业资质行政审批专栏-公告 records=10
OK 陕西建筑施工公告 records=20
OK 政策发布 records=10
OK 住房和城乡建设部行政规范性文件库 records=10
OK 建设工程企业资质行政审批专栏-部门规章 records=3
OK 建设工程企业资质行政审批专栏-资质标准 records=7
OK 建设工程企业资质行政审批专栏-政策文件 records=10
OK 建设工程企业资质行政审批专栏-审查意见公示 records=10
OK 建设工程企业资质行政审批专栏-通报 records=10
OK 工程建设项目审批制度改革工作-政策文件 records=10
OK 公告公示 records=10
OK 省厅文件 records=10
OK 陕西资质查询 records=20
```

## 质量检查

已通过：

```bash
ruff check .
ruff format --check .
pytest
```

测试结果：

```text
47 passed
```

本机未安装 `pwsh`，PowerShell 脚本语法解析未在 macOS 开发机执行。已通过测试检查 Windows 脚本文件存在、使用项目相对路径，并在 `docs/Windows本地部署说明.md` 中列明 Windows 实机验收步骤。

## 来源配置验证命令

已新增轻量来源验证命令：

```bash
zhengfudata validate-sources --limit 2
```

验证结果：

```text
OK section=1 records=10 strategy=http_with_retry name=建设工程企业资质行政审批专栏-公告
OK section=2 records=20 strategy=json_api name=陕西建筑施工公告
summary total=2 success=2 failed=0
```

说明：

- 该命令只请求列表页并验证是否能解析到记录。
- 不写入数据库。
- 不下载附件。
- 可用于 Windows 部署后的来源连通性验收。

## 13 个启用栏目完整来源验证

执行命令：

```bash
zhengfudata validate-sources
```

验证结果：

```text
summary total=13 success=13 failed=0
```

通过栏目：

```text
建设工程企业资质行政审批专栏-公告 records=10
陕西建筑施工公告 records=20
政策发布 records=10
住房和城乡建设部行政规范性文件库 records=10
建设工程企业资质行政审批专栏-部门规章 records=3
建设工程企业资质行政审批专栏-资质标准 records=7
建设工程企业资质行政审批专栏-政策文件 records=10
建设工程企业资质行政审批专栏-审查意见公示 records=10
建设工程企业资质行政审批专栏-通报 records=10
工程建设项目审批制度改革工作-政策文件 records=10
公告公示 records=10
省厅文件 records=10
陕西资质查询 records=20
```

## 小批量完整闭环验证

执行命令：

```bash
zhengfudata run-daily-crawl --limit 2
```

结果：

```text
daily sections=2 success=2 failed=0
notification=2 status=failed reason=OPENCLAW_WEBHOOK_URL 未配置
```

数据库验证：

```text
runs 8
announcements 30
attachments 35
notifications 2
recent runs:
section 1 success discovered=10 new=0 attachment_success=35 attachment_failed=0
section 2 success discovered=20 new=0 attachment_success=0 attachment_failed=0
attachment status: success 35
```

说明：

- 重复抓取未产生重复公告。
- 附件下载状态保持成功。
- OpenClaw 未配置时，通知失败原因可记录，不影响抓取任务成功入库。

## 定时任务类型验证

执行命令：

```bash
zhengfudata run-daily-crawl --limit 1 --no-notify
```

结果：

```text
daily sections=1 success=1 failed=0
latest run: scheduled-20260621215135385692-1 scheduled cli_daily success
```

说明：

- `cli_daily` 和应用内置定时触发会写入 `run_type=scheduled`。
- 普通后台或 CLI 单栏目抓取仍属于手动任务。

## 13 个启用栏目完整每日任务验收

执行命令：

```bash
zhengfudata run-daily-crawl --no-notify
```

结果：

```text
daily sections=13 success=13 failed=0
```

数据库验证：

```text
run ids: 36-48
sections 13 success 13 failed 0
discovered 140
new 0
content_changed 8
attachment_success 152
attachment_failed 0
attachment_added 0
attachment_changed 0
announcements 140
attachments 152
section15 announcements 20
local attachment files 152
storage size 25M
```

逐栏目结果：

```text
建设工程企业资质行政审批专栏-公告 success discovered=10 new=0 attachment_success=35 attachment_failed=0 duration=82s
陕西建筑施工公告 success discovered=20 new=0 attachment_success=0 attachment_failed=0 duration=8s
政策发布 success discovered=10 new=0 attachment_success=12 attachment_failed=0 duration=38s
住房和城乡建设部行政规范性文件库 success discovered=10 new=0 attachment_success=29 attachment_failed=0 duration=72s
建设工程企业资质行政审批专栏-部门规章 success discovered=3 new=0 attachment_success=6 attachment_failed=0 duration=24s
建设工程企业资质行政审批专栏-资质标准 success discovered=7 new=0 attachment_success=9 attachment_failed=0 duration=53s
建设工程企业资质行政审批专栏-政策文件 success discovered=10 new=0 attachment_success=1 attachment_failed=0 duration=23s
建设工程企业资质行政审批专栏-审查意见公示 success discovered=10 new=0 attachment_success=29 attachment_failed=0 duration=79s
建设工程企业资质行政审批专栏-通报 success discovered=10 new=0 attachment_success=0 attachment_failed=0 duration=26s
工程建设项目审批制度改革工作-政策文件 success discovered=10 new=0 attachment_success=11 attachment_failed=0 duration=43s
公告公示 success discovered=10 new=0 attachment_success=7 attachment_failed=0 duration=29s
省厅文件 success discovered=10 new=0 attachment_success=13 attachment_failed=0 duration=36s
陕西资质查询 success discovered=20 new=0 attachment_success=0 attachment_failed=0 duration=15s
```

说明：

- 13 个启用栏目已完成一次完整每日任务实测。
- 每个栏目任务状态均为 `success`，说明列表抓取、正文解析、入库流程完整跑通。
- 陕西资质查询已通过公开 JSON 接口接入，并归档 20 条企业资质记录。
- 附件记录共 152 条，152 个文件均已下载到 `storage/attachments`。
- 曾失败的住建部行政规范性文件库附件已修复，根因是下载 URL 中中文 `fileName` 参数需要在请求前做百分号编码。
- 本次使用 `--no-notify`，不触发 OpenClaw；真实企微群日报仍需配置 webhook 后单独验收。

## 后台页面验证

已启动本地服务并验证以下页面返回 200：

```text
/               工作台
/crawl-runs     抓取任务
/crawl-runs/9   抓取任务详情，显示 scheduled
/changes        变化记录，支持按变化类型、网站和栏目筛选
/attachments    附件管理，支持按关键词、状态、网站和本地文件筛选
/notifications  通知日志
```

## 系统配置页验证

已补充后台只读系统配置页：

```text
/settings 系统配置
```

页面可查看：

- 运行环境和数据库配置。
- storage 目录。
- 每日调度状态。
- OpenClaw 和企微通知配置状态。
- Windows 本地部署脚本状态。

安全约束：

- 不在页面明文展示 `APP_SECRET_KEY`。
- 不在页面明文展示 `ADMIN_PASSWORD`。
- 不在页面明文展示 `OPENCLAW_WEBHOOK_URL`。

## 自动验收报告导出

已新增命令：

```bash
zhengfudata export-acceptance-report
```

验证结果：

```text
acceptance_report=storage/exports/v1_acceptance_report_20260621_222916.md
```

报告包含：

- 环境和 storage 路径。
- 站点、栏目、公告、附件、任务和通知统计。
- 附件下载状态。
- 最近抓取任务。
- 最近通知日志。
- 后台页面验收入口。
- 失败任务、失败附件、失败通知和处理建议。
- V1 验收关注项和后续待验收项。

## Windows 部署交付物

已补充：

```text
scripts/windows/setup.ps1
scripts/windows/run-server.ps1
scripts/windows/run-daily-crawl.ps1
scripts/windows/validate-sources.ps1
scripts/windows/export-acceptance-report.ps1
scripts/windows/install-daily-task.ps1
docs/Windows本地部署说明.md
```

说明：

- 脚本均通过 `$PSScriptRoot` 自动定位项目根目录，不依赖固定本机路径。
- `setup.ps1` 负责创建虚拟环境、安装依赖、初始化 `.env`、执行迁移和导入首批站点。
- `run-server.ps1` 负责启动后台。
- `run-daily-crawl.ps1` 负责执行每日抓取。
- `validate-sources.ps1` 负责验证启用栏目列表页可访问且可解析。
- `export-acceptance-report.ps1` 负责导出自动验收报告。
- `install-daily-task.ps1` 负责注册 Windows 任务计划。

## 后台手动抓取入口

已补充后台触发入口：

- 网站和栏目表单提供服务端基础校验，错误配置不会入库。
- 工作台页面可直接点击“执行每日抓取”。
- 抓取任务页面可点击“执行每日抓取”。
- 抓取任务页面可勾选“发送日报”，同步触发 OpenClaw 通知。
- 网站栏目页可点击“抓取网站”，手动抓取该网站下所有启用栏目。
- 后台入口复用 `run_daily_crawl` 调度服务，避免另建一套抓取逻辑。

本轮自测结果：

```text
ruff check .                 PASS
ruff format --check .        PASS
pytest                       48 passed, 1 warning
```

新增测试覆盖：

- 未登录访问后台每日抓取触发入口会跳转登录页。
- 登录后触发每日抓取会进入调度服务。
- 勾选“发送日报”时，`notify=True` 会传入调度服务。
- 未登录访问单网站抓取入口会跳转登录页。
- 登录后触发单网站抓取只会执行该网站下启用栏目。
- 无效网站 URL、重复网站标识和非法请求头 JSON 会返回校验错误。
- 工作台和抓取任务页均展示后台手动触发入口。

## 附件更新时间与温和重试

已补充抓取细节：

- 附件下载成功时，如果目标站响应 `Last-Modified`，系统会保存到附件 `file_updated_at` 字段，便于后台和后续知识库追溯文件更新时间。
- 如果目标站没有返回 `Last-Modified`，系统保留已有更新时间，不用空值覆盖历史值。
- `http_with_retry` 失败重试时，会按栏目 `request_interval_seconds` 做递增等待，例如 2 秒、4 秒，避免短时间高频请求。

新增测试覆盖：

- 附件 `Last-Modified` 可解析并入库为文件更新时间。
- HTTP 连续失败后会按配置进行退避等待，再进入 curl 兜底请求。

## OpenClaw 通知失败重试

已补充通知可靠性能力：

- `OPENCLAW_NOTIFY_RETRY_TIMES` 可配置通知失败自动重试次数，默认 2 次。
- 每日抓取日报发送失败时，会自动重试，不影响抓取结果入库。
- 通知日志页提供“重试”按钮，可对失败通知手动重试。
- 手动重试会新建一条通知日志，保留原失败记录，便于追溯。
- 系统配置页展示当前通知重试次数。

新增测试覆盖：

- OpenClaw 首次发送失败、后续成功时，通知状态最终为 `success`。
- 手动重试会复用原通知 payload 并新建通知日志。
- 未登录访问通知重试入口会跳转登录页。
- 登录后触发通知重试会进入通知重试服务。

## 附件失败重试下载

已补充附件归档运维能力：

- 列表和正文抓取成功但附件失败时，任务状态标记为 `partial_success`。
- 附件列表展示失败原因。
- 附件管理页可将当前筛选下已保存的本地附件打包为 ZIP 下载。
- 附件列表和公告详情均提供原始附件地址入口。
- 附件列表和公告详情均提供“重试”按钮。
- 手动重试复用原附件所属站点、栏目和请求策略下载文件。
- 重试会创建独立手动任务，成功/失败进入抓取任务统计。

新增测试覆盖：

- 附件下载失败会把抓取任务标记为 `partial_success`。
- 附件打包下载只包含已保存到本地的附件文件。
- 失败附件可通过重试下载更新为 `success`。
- 重试成功后本地文件写入 `storage`，失败原因被清空。
- 未登录访问附件重试入口会跳转登录页。
- 登录后触发附件重试会进入附件重试服务。

## 任务详情通知状态

已补充抓取任务详情的通知闭环：

- 任务详情页展示与当前任务关联的通知日志。
- 可查看通知事件类型、发送状态、目标、响应状态码和失败原因。
- 通知失败时可从任务详情页直接点击“重试”。

新增测试覆盖：

- 抓取任务详情页展示“通知状态”区块。
- 抓取任务详情页可看到 OpenClaw 未配置失败原因。
- 抓取任务详情页提供通知重试入口。

## 后续验收事项

- 在 Windows 电脑按 `docs/Windows本地部署说明.md` 完成安装、启动、导入、抓取和附件下载验证。
- 配置真实 `OPENCLAW_WEBHOOK_URL` 后，验证企微群日报发送。
- 针对资质增项公告查询页面补 Playwright 或接口适配器。
