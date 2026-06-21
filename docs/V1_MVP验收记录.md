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
- Playwright 动态查询页面适配。
- 企微真实群日报发送。

## 首批来源配置

当前 `configs/sites.yaml` 已配置：

- 3 个站点。
- 14 个栏目。
- 12 个启用栏目。
- 2 个待适配动态查询页面，默认不启用。

待适配页面：

- 陕西资质查询：`https://qiye.sxxzsp.cn:29086/qualification`
- 陕西资质增项公告查询页面：`https://qiye.sxxzsp.cn:29086/affiche`

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
enabled_sections 12
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
40 passed
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

## 后台页面验证

已启动本地服务并验证以下页面返回 200：

```text
/               工作台
/crawl-runs     抓取任务
/crawl-runs/9   抓取任务详情，显示 scheduled
/attachments    附件管理
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

## Windows 部署交付物

已补充：

```text
scripts/windows/setup.ps1
scripts/windows/run-server.ps1
scripts/windows/run-daily-crawl.ps1
scripts/windows/validate-sources.ps1
scripts/windows/install-daily-task.ps1
docs/Windows本地部署说明.md
```

说明：

- 脚本均通过 `$PSScriptRoot` 自动定位项目根目录，不依赖固定本机路径。
- `setup.ps1` 负责创建虚拟环境、安装依赖、初始化 `.env`、执行迁移和导入首批站点。
- `run-server.ps1` 负责启动后台。
- `run-daily-crawl.ps1` 负责执行每日抓取。
- `validate-sources.ps1` 负责验证启用栏目列表页可访问且可解析。
- `install-daily-task.ps1` 负责注册 Windows 任务计划。

## 后续验收事项

- 在 Windows 电脑按 `docs/Windows本地部署说明.md` 完成安装、启动、导入、抓取和附件下载验证。
- 配置真实 `OPENCLAW_WEBHOOK_URL` 后，验证企微群日报发送。
- 针对待适配动态查询页面补 Playwright 或接口适配器。
- 逐步扩大到 12 个启用栏目，完成一次完整每日任务验收。
