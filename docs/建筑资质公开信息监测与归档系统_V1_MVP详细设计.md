# 建筑资质公开信息监测与归档系统 V1 MVP 详细设计

## 1. 项目背景

本系统用于监测国家及地方政府公开网站中与建筑企业资质相关的信息，自动抓取公开页面内容和附件，识别新增公告、正文变化、附件变化，并将结果归档到本地知识库中。

V1 阶段重点解决“抓得到、存得住、看得见、能通知、可追溯”的问题。系统先以轻量单机版方式运行，支持本地存储、后台查看、每日定时抓取和 OpenClaw 集成企微通知。

后续 V2/V3 可在此基础上扩展知识库问答、资质报告生成、企业申报辅助、云端部署等能力。

## 2. V1 目标与边界

### 2.1 V1 目标

V1 建设一个轻量 MVP，支持以下能力：

- 管理几十个政府公开网站及其栏目，后续可持续新增。
- 每天定时抓取建筑资质相关公开信息。
- 抓取内容包括资质公告、政府文件、行政许可、企业名单、考试人员公告等。
- 自动识别新增信息、正文变化、附件新增、附件变化。
- 自动下载 Word、Excel、PDF 附件。
- 保存原始地址、页面内容、附件文件、文件更新时间、抓取时间等信息。
- 将结构化数据和附件归档到本地 `storage/` 目录。
- 后台可查看抓取数据、附件、任务统计、失败原因。
- 后台可跳转原始政府网站，可下载附件。
- 抓取完成后通过 OpenClaw 通知企业微信群机器人。

### 2.2 V1 不做的内容

V1 暂不建设以下能力：

- 不做资质标准库。
- 不做企业档案。
- 不做企业资质申报辅助。
- 不做智能问答。
- 不做自动生成资质报告。
- 不做全文检索。
- 不做复杂权限体系。
- 不做多租户。
- 不做云存储，但预留迁移能力。
- 不做验证码绕过、登录绕过、高频对抗式反爬。

## 3. 系统架构

### 3.1 总体架构

```text
政府公开网站
    ↓
采集服务
    ↓
解析与变化检测
    ↓
SQLite 数据库 + 本地 storage 文件存储
    ↓
后台管理系统
    ↓
OpenClaw
    ↓
企业微信群机器人
```

### 3.2 应用架构

V1 推荐采用轻量单体架构：

```text
FastAPI 应用
  ├─ 后台页面
  ├─ API 接口
  ├─ 简单账号密码登录
  ├─ 定时任务调度
  ├─ 网站源管理
  ├─ 网页采集器
  ├─ 页面解析器
  ├─ 变化检测器
  ├─ 附件下载器
  ├─ 本地文件归档
  ├─ OpenClaw 通知集成
  └─ 数据库管理
```

### 3.3 推荐技术栈

```text
后端框架：Python FastAPI
后台页面：Jinja2 + Bootstrap
数据库：SQLite
任务调度：APScheduler
网页抓取：httpx + BeautifulSoup
动态页面：Playwright 按需使用
文件存储：本地 storage 目录
通知集成：OpenClaw
```

后续升级路径：

```text
SQLite -> PostgreSQL
本地文件 -> 云对象存储
APScheduler -> Celery / Redis
Jinja2 后台 -> Vue / React
结构化归档 -> 全文检索 / 向量知识库
```

### 3.4 开源底座取舍

V1 不以 ArchiveBox、Crawlab、ScrapydWeb、Gerapy 等开源项目作为主工程底座进行 fork 二开，而采用自研轻量单体应用。

原因如下：

- 系统核心对象是“公告、附件、来源、抓取批次、变化事件”，不是单纯的 URL 快照。
- ArchiveBox 更适合作为网页归档工具参考，不适合作为资质公告业务系统主数据模型。
- Crawlab 等爬虫平台更适合多爬虫、多节点和团队化调度，V1 单机 MVP 使用成本偏高。
- 自研轻量单体可以更快闭环后台管理、附件归档、企微通知和后续知识库结构。

V1 可参考开源项目的局部设计：

- 参考 ArchiveBox 的归档目录、快照保存、文件命名和长期保存思路。
- 参考 changedetection.io 的变化检测、通知触发和页面选择器配置思路。
- 后续当网站规模、并发或运维复杂度上升时，再评估是否接入 Crawlab 等任务管理平台。

## 4. 核心模块设计

### 4.1 网站源管理模块

用于维护需要抓取的政府网站和栏目。

网站级信息：

- 网站名称
- 网站首页地址
- 主管单位
- 地区
- 是否启用
- 备注
- 最近抓取时间
- 最近抓取状态
- 创建时间
- 更新时间

栏目级信息：

- 所属网站
- 栏目名称
- 栏目地址
- 信息类型
- 抓取方式
- 爬虫策略
- 是否启用
- 是否下载附件
- 是否保存页面快照
- 列表页解析规则
- 详情页解析规则
- 分页规则
- 附件规则
- 最近抓取时间
- 最近抓取状态
- 最近失败原因

后台需要支持：

- 新增网站
- 编辑网站
- 启用 / 停用网站
- 新增栏目
- 编辑栏目
- 启用 / 停用栏目
- 手动触发栏目抓取
- 查看最近抓取状态和失败原因

### 4.2 抓取任务调度模块

V1 采用固定频率：每天定时抓取一次。

任务类型：

- 每日定时抓取
- 手动全量抓取
- 手动单网站抓取
- 手动单栏目抓取

任务状态：

- `pending`：等待中
- `running`：执行中
- `success`：成功
- `partial_success`：部分成功
- `failed`：失败

任务统计字段：

- 任务开始时间
- 任务结束时间
- 耗时
- 计划抓取栏目数
- 成功栏目数
- 失败栏目数
- 发现信息数
- 新增信息数
- 正文变化数
- 附件新增数
- 附件变化数
- 附件下载成功数
- 附件下载失败数
- 失败地址
- 失败原因

### 4.3 网页采集模块

负责获取列表页、详情页、附件响应和页面快照。

采集优先级：

```text
优先普通 HTTP 抓取
需要请求头或重试时启用增强 HTTP 策略
动态页面使用 Playwright 渲染
特殊网站使用定制适配器
```

需要处理：

- 页面编码识别
- 相对链接转绝对链接
- 请求超时
- 失败重试
- 页面 403 / 404 / 500
- 附件链接跳转
- 文件名乱码
- Windows 非法文件名字符清理

默认配置：

- 请求超时：30 秒
- 失败重试：2 次
- 请求间隔：2 秒
- 支持文件类型：`.doc`、`.docx`、`.xls`、`.xlsx`、`.pdf`

### 4.4 内容解析模块

负责将网页转换为结构化信息。

信息字段：

- 标题
- 信息类型
- 来源网站
- 来源栏目
- 原始地址
- 最终访问地址
- 发布时间
- 页面更新时间
- 正文内容
- 正文摘要
- 附件列表
- 抓取时间

解析规则来源：

- 后台配置规则
- 通用解析规则
- 定制适配器

信息类型枚举：

- `qualification_notice`：资质公告
- `government_file`：政府文件
- `administrative_license`：行政许可
- `company_list`：企业名单
- `exam_personnel_notice`：考试人员公告
- `other`：其他

V1 可先由栏目配置决定默认信息类型，后续再增加自动分类。

### 4.5 变化检测模块

V1 重点识别：

- 新增公告
- 正文变化
- 附件新增
- 附件变化
- 抓取失败
- 附件下载失败

唯一识别优先级：

```text
1. 原始详情页 URL
2. 标题 + 发布时间 + 来源栏目
3. 标题 + 来源栏目
```

Hash 规则：

- 正文 hash：清洗后的正文文本 hash。
- 附件 hash：下载后的文件内容 hash。
- 附件列表 hash：附件名称 + 附件链接集合 hash。

变化类型：

- `new_item`：新增信息
- `content_changed`：正文变化
- `attachment_added`：附件新增
- `attachment_changed`：附件内容变化
- `metadata_changed`：标题、日期等元信息变化
- `no_change`：无变化
- `crawl_failed`：抓取失败
- `attachment_failed`：附件下载失败

判断规则：

- 唯一标识不存在，视为新增信息。
- 正文 hash 变化，视为正文变化。
- 附件列表出现新附件，视为附件新增。
- 附件文件 hash 变化，视为附件变化。
- 仅抓取时间变化，不视为业务变化。

### 4.6 附件下载与归档模块

负责下载并保存 Word、Excel、PDF 附件。

附件字段：

- 附件名称
- 附件类型
- 原始下载地址
- 最终下载地址
- 所属信息
- 所属网站
- 本地文件路径
- 文件大小
- 文件 hash
- 文件更新日期
- 下载时间
- 下载状态
- 失败原因

下载状态：

- `pending`：待下载
- `success`：成功
- `failed`：失败
- `skipped`：跳过

归档规则：

```text
storage/
  attachments/
    {site_slug}/
      {year}/
        {item_id}/
          {attachment_id}_{safe_filename}
  snapshots/
    {site_slug}/
      {year}/
        {item_id}.html
  exports/
  logs/
```

数据库中存储相对路径，系统配置中存储 `storage` 根目录，避免未来部署环境变化导致路径失效。

### 4.7 后台管理模块

V1 后台面向少数内部人员使用，先做简单账号密码登录，不做复杂权限。

#### 首页统计

展示：

- 今日新增
- 今日正文变化
- 今日附件变化
- 今日抓取失败
- 今日附件失败
- 最近一次抓取时间
- 最近任务状态

#### 抓取信息列表

展示字段：

- 标题
- 信息类型
- 来源网站
- 来源栏目
- 发布时间
- 页面更新时间
- 抓取时间
- 状态
- 附件数量
- 原始链接
- 详情入口

筛选条件：

- 网站
- 栏目
- 信息类型
- 状态
- 是否有附件
- 发布时间范围
- 抓取时间范围

#### 信息详情页

展示：

- 标题
- 来源网站
- 来源栏目
- 原始地址
- 最终地址
- 发布时间
- 页面更新时间
- 抓取时间
- 正文内容
- 附件列表
- 变化记录
- 页面快照
- 跳转原始系统按钮

#### 附件管理页

展示：

- 附件名称
- 所属信息
- 来源网站
- 文件类型
- 文件大小
- 下载状态
- 下载时间
- 文件更新时间
- 原始下载地址
- 本地下载入口
- 失败原因
- 重试下载入口

#### 抓取任务记录页

展示：

- 任务编号
- 任务类型
- 开始时间
- 结束时间
- 状态
- 成功栏目数
- 失败栏目数
- 新增数量
- 变化数量
- 附件成功数量
- 附件失败数量
- 详情入口

#### 网站源管理页

展示和管理：

- 网站列表
- 栏目列表
- 新增 / 编辑
- 启用 / 停用
- 手动抓取
- 最近抓取状态
- 最近失败原因

### 4.8 OpenClaw 通知集成模块

V1 中 OpenClaw 作为企微通知入口，不承担抓取、存储、变化检测和知识库管理。

系统职责：

- 抓取系统生成结构化通知事件。
- 抓取系统将通知事件发送给 OpenClaw。
- OpenClaw 将通知转发到企业微信群机器人。

通知触发：

- 定时任务完成
- 手动任务完成
- 出现新增信息
- 出现正文变化
- 出现附件变化
- 出现抓取失败
- 出现附件下载失败

通知事件接口：

```text
POST {OPENCLAW_WEBHOOK_URL}
```

消息体示例：

```json
{
  "event_type": "crawl_result",
  "task_id": "202606160001",
  "finished_at": "2026-06-16 10:30:00",
  "status": "partial_success",
  "total_sections": 12,
  "success_sections": 11,
  "failed_sections": 1,
  "new_items": 8,
  "content_changed_items": 2,
  "attachment_added": 3,
  "attachment_changed": 1,
  "attachment_failed": 1,
  "detail_url": "http://localhost:8000/tasks/202606160001",
  "top_items": [
    {
      "title": "xxx建筑业企业资质核准公告",
      "source": "xxx住建厅",
      "url": "http://example.com/detail"
    }
  ],
  "failures": [
    {
      "url": "http://example.com/list",
      "reason": "请求超时"
    }
  ]
}
```

后续预留 OpenClaw 调用系统接口：

```text
GET /api/recent-items
GET /api/tasks/{task_id}
GET /api/items/{item_id}
GET /api/attachments/{attachment_id}/download
```

V2/V3 可继续扩展：

```text
POST /api/kb/ask
POST /api/reports/generate
POST /api/files/generate
```

### 4.9 抓取范围与任务并发控制

V1 每天固定抓取一次，但需要控制每次抓取范围，避免每天重复抓取大量历史分页，导致任务越来越慢。

栏目级抓取范围配置：

- 最大抓取页数。
- 单次最大抓取信息数量。
- 连续遇到已存在信息后的停止数量。
- 抓取日期窗口，例如只抓最近 N 天或最近 N 个月。
- 是否允许抓取全部分页，默认不允许。

默认建议：

```text
max_pages=3
max_items_per_run=100
stop_when_seen_existing_count=20
crawl_date_window_days=180
allow_full_crawl=false
```

抓取停止规则：

- 达到最大页数时停止。
- 达到单次最大信息数量时停止。
- 连续遇到指定数量的已存在信息时停止。
- 信息发布时间早于抓取日期窗口时停止。
- 列表页无更多详情链接时停止。

任务并发控制：

- 同一栏目同一时间只允许一个运行中任务。
- 定时任务运行中时，后台手动触发同一栏目应提示已有任务运行中。
- 全量任务运行中时，不允许重复启动另一个全量任务。
- 单个栏目失败不影响其他栏目继续执行。
- 应用重启后，如果存在长时间未结束的 running 任务，应标记为异常中断。

### 4.10 配置校验与测试抓取

后台新增或编辑网站栏目时，需要提供基础校验，减少错误配置进入正式任务。

配置保存校验：

- URL 格式校验。
- 请求头 JSON 格式校验。
- 爬虫策略枚举值校验。
- 抓取范围数值校验。
- 选择器不能为空的场景需要提示。
- 定制适配器名称需要匹配已存在适配器。

测试抓取功能：

- 后台提供“测试抓取”按钮。
- 测试抓取默认不入库。
- 测试抓取展示列表页请求状态。
- 展示解析到的详情链接数量。
- 展示前几条标题、日期、详情地址。
- 展示详情页正文片段。
- 展示解析到的附件名称和附件地址。
- 展示失败原因和错误堆栈摘要。

通过测试抓取后，再启用正式定时抓取。

### 4.11 通知日志与失败重试

OpenClaw 通知属于业务闭环的一部分，需要记录通知状态。

通知处理要求：

- OpenClaw 地址为空时，不影响抓取任务完成，但记录为未配置通知。
- 通知发送失败时，不影响抓取数据入库。
- 通知失败需要记录状态码、响应内容、失败原因。
- 通知失败默认重试 2 次。
- 后台任务详情页展示通知状态。
- 通知失败可在后台手动重试。

## 5. 爬虫策略设计

### 5.1 策略类型

V1 定义以下爬虫策略，每个栏目可独立配置：

```text
http_static
普通静态页面抓取，优先使用。

http_with_headers
带请求头、Referer、User-Agent 等配置的普通抓取。

http_with_retry
适合偶发失败的网站，支持超时、重试、退避等待。
退避等待按栏目 `request_interval_seconds` 递增执行，避免失败时高频请求目标网站。

browser_rendered
使用 Playwright 渲染页面，适合动态加载的网站。

custom_adapter
定制适配器，适合分页复杂、附件跳转特殊、接口特殊的网站。

manual_import
预留策略，未来可手动导入网页或附件。
```

### 5.2 策略选择原则

```text
优先 http_static
不稳定时使用 http_with_headers 或 http_with_retry
动态页面使用 browser_rendered
极特殊网站使用 custom_adapter
人工补录场景预留 manual_import
```

### 5.3 反爬与限制处理原则

V1 只做合规、温和、稳定的公开信息抓取。

允许的处理：

- 请求间隔
- 请求重试
- User-Agent 配置
- Referer 配置
- Accept-Language 配置
- 请求超时配置
- 每天固定低频抓取
- 普通请求失败后降级为浏览器渲染
- 记录 403、404、500、超时、解析失败、附件失败等错误

不做的处理：

- 不绕过验证码。
- 不绕过登录。
- 不进行高频请求。
- 不进行对抗式规避。
- 不抓取非公开内容。

### 5.4 栏目级策略配置

栏目可配置：

- 爬虫策略
- 请求超时时间
- 重试次数
- 请求间隔
- 自定义请求头
- 是否使用浏览器渲染
- 是否下载附件
- 是否保存页面快照
- 定制适配器名称

## 6. 数据库设计

V1 使用 SQLite。以下为核心表设计。

### 6.1 sites 网站表

```text
id
name
slug
homepage_url
organization
region
enabled
remark
last_crawled_at
last_status
created_at
updated_at
```

### 6.2 site_sections 栏目表

```text
id
site_id
name
url
item_type
crawl_method
crawler_strategy
schedule_cron
enabled
download_attachments
save_snapshot
request_timeout
retry_times
request_interval_seconds
request_headers
max_pages
max_items_per_run
stop_when_seen_existing_count
crawl_date_window_days
allow_full_crawl
list_selector
title_selector
date_selector
detail_url_selector
content_selector
attachment_selector
pagination_rule
custom_adapter
last_crawled_at
last_status
last_error
created_at
updated_at
```

### 6.3 crawl_tasks 抓取任务表

```text
id
task_no
task_type
status
started_at
finished_at
duration_seconds
total_sections
success_sections
failed_sections
discovered_items
new_items
content_changed_items
attachment_added_count
attachment_changed_count
attachment_success_count
attachment_failed_count
triggered_by
error_summary
created_at
updated_at
```

### 6.4 crawl_task_logs 任务日志表

```text
id
task_id
site_id
section_id
level
message
url
error_detail
created_at
```

### 6.5 crawl_items 信息表

```text
id
site_id
section_id
task_id
identity_key
identity_strategy
title
item_type
source_url
final_url
raw_published_at
published_at
raw_page_updated_at
page_updated_at
fetched_at
status
content
content_summary
content_hash
attachments_hash
snapshot_path
first_seen_at
last_seen_at
created_at
updated_at
```

### 6.6 item_versions 信息版本表

```text
id
item_id
task_id
version_no
title
published_at
page_updated_at
content
content_hash
attachments_hash
snapshot_path
change_type
created_at
```

### 6.7 attachments 附件表

```text
id
item_id
site_id
task_id
attachment_key
name
safe_name
file_ext
mime_type
source_url
final_url
local_path
file_size
file_hash
file_updated_at
downloaded_at
download_status
failure_reason
first_seen_at
last_seen_at
created_at
updated_at
```

`file_updated_at` 优先取附件响应头 `Last-Modified`。目标站未返回该响应头时，保留已有更新时间，不用空值覆盖历史记录。

### 6.8 attachment_versions 附件版本表

```text
id
attachment_id
announcement_id
site_id
run_id
version_no
name
safe_name
source_url
final_url
local_path
file_size
file_hash
file_updated_at
downloaded_at
download_status
change_type
created_at
updated_at
```

V1 中仅在附件首次成功下载、失败后首次成功下载或文件 hash 变化时新增版本记录；重复抓取到相同文件 hash 不新增版本，避免无意义膨胀。

### 6.9 change_logs 变化记录表

```text
id
task_id
item_id
attachment_id
change_type
title
source_url
old_hash
new_hash
description
created_at
```

### 6.10 notification_logs 通知日志表

```text
id
task_id
event_type
target_url
request_payload
response_status
response_body
status
retry_count
failure_reason
sent_at
created_at
updated_at
```

### 6.11 app_settings 系统配置表

```text
id
key
value
description
updated_at
```

## 7. 文件存储设计

### 7.1 存储原则

- 附件文件不存入数据库。
- 数据库存储文件相对路径。
- `storage` 根目录通过配置项指定。
- 原始文件名保留，实际保存文件名使用安全文件名。
- 路径拼接必须使用跨平台方式，兼容 Windows 和 macOS/Linux。

### 7.2 目录结构

```text
storage/
  attachments/
    {site_slug}/
      {year}/
        {item_id}/
          {attachment_id}_{safe_filename}
  snapshots/
    {site_slug}/
      {year}/
        {item_id}.html
  exports/
  logs/
```

### 7.3 文件名规则

文件名需要清理 Windows 非法字符：

```text
< > : " / \ | ? *
```

同时需要处理：

- 文件名过长
- 文件名为空
- 文件名重复
- 中文文件名编码异常
- URL 中无法提取文件名

## 8. 配置项设计

### 8.1 应用级配置

建议通过 `.env` 或配置文件管理：

```text
APP_NAME=建筑资质公开信息监测与归档系统
APP_BASE_URL=http://localhost:8000
APP_STORAGE_ROOT=storage
DATABASE_URL=sqlite:///data/app.db

ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me

OPENCLAW_WEBHOOK_URL=

DEFAULT_CRAWL_TIME=02:00
DEFAULT_REQUEST_TIMEOUT=30
DEFAULT_RETRY_TIMES=2
DEFAULT_REQUEST_INTERVAL_SECONDS=2
DEFAULT_USER_AGENT=
```

### 8.2 网站栏目配置

可通过后台维护，必要时也可支持配置文件导入：

```text
网站名称
栏目名称
栏目地址
信息类型
爬虫策略
是否启用
是否下载附件
是否保存快照
请求超时
重试次数
请求间隔
请求头配置
列表选择器
标题选择器
日期选择器
详情链接选择器
正文选择器
附件选择器
分页规则
定制适配器名称
```

## 9. 核心流程设计

### 9.1 每日定时抓取流程

```text
1. 调度器按固定时间触发任务。
2. 创建 crawl_tasks 记录。
3. 查询启用的网站栏目。
4. 按栏目读取爬虫策略和解析规则。
5. 抓取列表页。
6. 提取详情页链接。
7. 抓取详情页。
8. 解析标题、正文、日期、附件。
9. 保存页面快照。
10. 执行去重和变化检测。
11. 新增或更新 crawl_items。
12. 写入 item_versions。
13. 下载附件。
14. 写入 attachments 和 attachment_versions。
15. 写入 change_logs。
16. 更新任务统计。
17. 发送 OpenClaw 通知。
18. 后台展示任务结果。
```

### 9.2 手动抓取流程

```text
1. 用户在后台点击手动抓取。
2. 系统创建手动任务。
3. 执行指定网站或栏目的抓取。
4. 后续流程与每日定时抓取一致。
```

### 9.3 附件下载流程

```text
1. 从详情页解析附件链接。
2. 判断文件类型是否支持。
3. 转换为绝对链接。
4. 请求附件地址。
5. 获取最终下载地址。
6. 保存到本地目录。
7. 计算文件 hash。
8. 判断是否新增或变化。
9. 更新附件记录。
10. 失败则记录原因。
```

### 9.4 失败处理流程

```text
1. 抓取失败时记录失败 URL、错误类型和错误详情。
2. 附件失败时记录附件 URL、所属信息和失败原因。
3. 单个栏目失败不影响其他栏目继续执行。
4. 任务完成后根据成功和失败情况标记 success、partial_success 或 failed。
5. 失败信息进入后台任务详情和 OpenClaw 通知。
```

## 10. Windows 兼容设计

V1 需要考虑未来在 Windows 上部署运行。

设计要求：

- 所有路径使用程序跨平台路径拼接，不手写 `/` 或 `\`。
- 数据库存储相对路径，不依赖某台电脑的绝对路径。
- `storage` 根目录通过配置指定。
- 文件名清理 Windows 非法字符。
- 后台展示逻辑路径和下载入口，不直接暴露本机绝对路径。
- 定时任务使用应用内部调度，不依赖 Linux cron。
- V1 使用 `APP_SCHEDULER_ENABLED` 控制定时任务是否随应用启动，使用 `APP_SCHEDULER_DAILY_TIME` 配置每日固定抓取时间。
- Windows 上可选择常驻 FastAPI 应用内置调度，也可通过 Windows 任务计划调用 `zhengfudata run-daily-crawl` 做兜底。
- 配置项中不要写死 macOS 或 Linux 路径。
- 后续如需部署为 Windows 服务，可在部署阶段补充服务管理方案。

## 11. MVP 项目结构建议

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
```

## 12. 实施顺序

V1 按“先跑通业务闭环，再补后台和策略扩展”的方式开发。每个阶段完成后都需要有可运行结果、测试记录和验收结果，不以代码写完作为完成标准。

### 12.1 M0 项目底座与开发规范

目标：建立可持续开发的最小工程底座。

开发任务：

1. 初始化 Python 项目结构，不基于 ArchiveBox fork。
2. 配置 FastAPI、SQLite、SQLAlchemy、Alembic、Jinja2、APScheduler。
3. 建立 `.env` / `config.yaml` 配置读取机制。
4. 建立 `storage/`、`data/`、`logs/` 默认目录。
5. 配置跨平台路径处理，禁止硬编码 macOS、Linux 或 Windows 绝对路径。
6. 建立基础测试命令和代码格式化命令。
7. 编写 Windows 本地运行说明草稿。

验收条件：

- 新电脑拉取项目后，可以按文档创建环境并启动服务。
- `storage` 根目录、数据库路径、OpenClaw 地址均可配置。
- Windows 非法文件名清理函数有单元测试。

### 12.2 M1 数据模型与基础后台

目标：先把业务对象立起来，避免后续被“网页 URL 快照模型”绑住。

开发任务：

1. 建立核心表：`users`、`sites`、`site_sections`、`crawl_runs`、`announcements`、`attachments`、`change_logs`、`notification_logs`。
2. 实现简单账号密码登录。
3. 实现网站和栏目新增、编辑、启用、停用。
4. 实现栏目抓取策略配置字段。
5. 实现后台基础布局和导航。

验收条件：

- 后台可以登录。
- 后台可以维护政府网站和栏目。
- 数据库中可保存栏目策略、抓取频率、存储路径配置。

### 12.3 M2 抓取核心闭环

目标：用现有已验证的抓取逻辑重构为正式模块，先跑通 1 到 2 个真实站点。

开发任务：

1. 将现有 `june_archive.py` 中的请求、解析、附件下载能力拆分为服务模块。
2. 实现静态列表页抓取策略。
3. 实现 JSON API 抓取策略。
4. 实现受限站点说明型策略，用于记录不可抓原因。
5. 接入陕西资质增项公告接口。
6. 接入住建部一个静态公告栏目。
7. 实现公告解析、去重、入库。
8. 实现页面 HTML 快照保存。
9. 实现附件下载和 hash 计算。

验收条件：

- 可手动触发单个栏目抓取。
- 至少 2 个真实栏目可成功入库。
- 公告、附件、原始地址、本地路径、抓取批次能正确关联。
- 不可抓站点不会导致整批失败，而是形成可读失败原因。

### 12.4 M3 变化检测与任务统计

目标：把“今天新增/变化了什么”变成系统能力。

开发任务：

1. 实现公告唯一键规则。
2. 实现新增公告检测。
3. 实现正文 hash 对比。
4. 实现附件 URL、文件名、hash 对比。
5. 实现抓取批次统计：成功、失败、部分成功、记录数、附件数。
6. 实现失败日志和错误分类。

验收条件：

- 重复抓取同一批数据不会重复入库。
- 新公告会生成 `change_logs`。
- 正文变化和附件变化可被识别。
- 抓取运行详情中能看到成功数、失败数、失败地址和失败原因。

### 12.5 M4 后台查询与本地归档体验

目标：让少数内部用户能直接查看和下载归档结果。

开发任务：

1. 实现公告列表页。
2. 实现公告详情页。
3. 实现附件列表和下载入口。
4. 实现抓取任务列表和任务详情。
5. 实现按网站、栏目、日期、变化类型筛选。
6. 实现跳转原始政府网站。
7. 实现本地归档目录与数据库记录一致性检查。

验收条件：

- 用户可以在后台看到所有抓取公告。
- 用户可以打开详情、下载附件、跳转原始地址。
- 后台不直接暴露本机绝对路径，只通过下载接口访问文件。

### 12.6 M5 OpenClaw 企微通知

目标：形成“抓取完成 -> 日报 -> 企微通知”的业务闭环。

开发任务：

1. 实现通知配置：OpenClaw 地址、企微目标类型、目标用户或群 chatid。
2. 实现通知内容生成器。
3. 实现 OpenClaw 通知适配器。
4. 记录通知发送状态和失败原因。
5. 支持通知失败不影响抓取结果入库。

验收条件：

- 抓取完成后可向企微单聊或群聊发送日报。
- 通知内容包含新增数、变化数、附件数、失败数和后台入口。
- OpenClaw 未配置或发送失败时，后台能看到明确原因。

### 12.7 M6 扩展站点与端到端验收

目标：把 MVP 从“能跑”推进到“可交付试用”。

开发任务：

1. 接入 Excel 中已整理的首批 10 个左右网站或栏目。
2. 为不同网站补充静态页、JSON API、受限说明等策略配置。
3. 完成端到端测试：手动抓取、定时抓取、去重、变化检测、附件下载、后台查看、企微通知。
4. 补充 Windows 运行验证。
5. 输出部署说明、使用说明和验收记录。

验收条件：

- 至少 10 个网站或栏目完成配置。
- 至少 1 次完整定时任务跑通。
- `zhengfudata run-daily-crawl` 可手动触发每日任务闭环。
- 验收记录中包含成功来源、失败来源、失败原因和后续处理建议。

当前首批配置状态：

- `configs/sites.yaml` 已接入 Excel 中可直接监测的 13 个启用栏目。
- 已覆盖住房和城乡建设部政策发布、行政规范性文件库、建设工程企业资质行政审批专栏多个子栏目。
- 已覆盖陕西省住房和城乡建设厅公告公示、省厅文件、陕西建筑施工公告 JSON 接口和陕西资质查询 JSON 接口。
- 陕西资质增项公告查询页面属于查询型动态页面，已保留为 `browser_rendered` 待适配配置，默认不启用。

## 13. 开发设计 Review

### 13.1 从业务建模角度

当前设计应坚持以公告和附件为核心，而不是以 URL 快照为核心。这样后续做知识库、企业资质报告、附件解析时，数据关系更清晰。

需要注意：

- `announcements` 必须能关联来源网站、栏目、抓取批次和附件。
- `attachments` 必须独立建模，不能只作为公告 JSON 字段存储。
- `change_logs` 要记录变化类型和变化前后摘要，方便企微日报和后续审计。

### 13.2 从 MVP 交付风险角度

最大风险不是后台页面，而是不同政府网站页面结构不一致。

开发策略应调整为：

- 先实现 2 个真实站点闭环，再扩展后台完整功能。
- 抓取策略必须可配置、可插拔，不要把每个网站逻辑堆在一个脚本里。
- 对不可抓、无历史日期、HTTP 521 等情况要定义“说明型结果”，不能简单报错。

### 13.3 从 Windows 部署角度

Windows 本地运行是 V1 需要兼容的方向。

需要提前约束：

- 路径全部使用 `pathlib`。
- 文件名统一清理 Windows 非法字符。
- 不依赖 Linux cron。
- `curl`、Playwright 浏览器、Python 版本都要在部署文档中明确。
- 数据库存储相对路径，后台下载通过接口，不暴露本机绝对路径。

### 13.4 从通知集成角度

OpenClaw 适合作为通知和后续企微问答入口，但 V1 不应把抓取、存储和变化检测放进 OpenClaw。

需要注意：

- 通知模块只接收系统生成的通知事件。
- 企微群通知需要配置真实群 `chatid`。
- 通知失败不能影响抓取任务成功入库。
- 后续可保留备用通知适配器，例如直接企微 Webhook。

### 13.5 从后续知识库扩展角度

V1 暂不做全文检索和智能问答，但数据结构要为 V2/V3 留口。

需要预留：

- 公告正文纯文本字段。
- 附件内容解析状态。
- 文件 hash 和版本。
- 原始地址与本地快照的稳定映射。
- 后续向量化或全文索引的任务状态字段。

## 14. 验收标准

V1 MVP 完成后，应满足以下验收条件：

- 可通过后台新增和编辑政府网站。
- 可通过后台新增和编辑栏目。
- 可为栏目配置爬虫策略。
- 可每天定时抓取一次。
- 可手动触发网站或栏目抓取。
- 可抓取至少 10 个政府网站或栏目。
- 可保存标题、正文、发布时间、页面更新时间、原始地址、抓取时间。
- 可识别新增公告。
- 可识别正文变化。
- 可识别附件新增。
- 可识别附件内容变化。
- 可下载 Word、Excel、PDF 附件。
- 可记录附件原始地址、本地路径、下载状态、文件 hash。
- 可查看抓取成功、失败、部分成功状态。
- 可在后台查看所有抓取数据。
- 可在后台跳转原始政府网站。
- 可在后台下载附件。
- 可查看失败地址和失败原因。
- 可通过 OpenClaw 向企微发送抓取结果通知。
- 文件存储路径可配置。
- 在设计上兼容未来 Windows 部署。

### 14.1 开发完成定义

单个功能或里程碑只有同时满足以下条件，才算开发完成：

- 功能代码已实现，后台入口、CLI 命令或服务接口可实际触发。
- 数据库 model、migration、配置项和 `.env.example` 已同步。
- 单元测试覆盖核心逻辑，外部网站抓取测试不依赖实时网络。
- 本地通过 `ruff check .`、`ruff format --check .`、`pytest`。
- 涉及数据库变更时通过 `alembic upgrade head`。
- 涉及页面时完成一次人工页面检查。
- 文档同步更新，包含使用方式、配置项和已知限制。

### 14.2 最终测试与验收条件

V1 交付验收前，需要形成一份验收记录，至少包含：

- 环境信息：操作系统、Python 版本、数据库路径、storage 路径。
- 站点信息：已接入的网站和栏目数量，成功栏目、失败栏目、受限栏目清单。
- 抓取结果：新增公告数、正文变化数、附件新增数、附件变化数、附件成功和失败数。
- 后台验证：公告列表、公告详情、附件下载、抓取任务详情、通知日志均可访问。
- 通知验证：OpenClaw 企微日报可发送，未配置或发送失败时后台有明确日志。
- Windows 验证：路径、文件名、SQLite、本地附件下载在 Windows 上可运行。
- 未解决问题：失败网址、失败原因、是否属于目标网站限制，以及后续处理建议。

## 15. 后续阶段规划

### 15.1 V2 建议方向

- 附件内容解析。
- 普通关键词检索。
- 知识库问答入口。
- OpenClaw 企微问答。
- 政策和公告分类增强。
- 抓取适配器管理增强。

### 15.2 V3 建议方向

- 资质标准库。
- 企业档案。
- 企业资质申报辅助。
- 自动生成资质分析报告。
- 自动生成申报材料清单。
- Word / Excel 文件导出。
- 云端部署和对象存储。
