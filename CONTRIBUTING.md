# 团队开发规范

本文用于约束建筑资质公开信息监测与归档系统的多人协作开发。目标是让每个阶段都能交付可运行、可测试、可验收的结果。

## 1. 开发前必读

开发前必须阅读：

1. `docs/建筑资质公开信息监测与归档系统_V1_MVP详细设计.md`
2. `docs/建筑资质公开信息监测与归档系统_前端UI详细设计.md`
3. `README.md`
4. 本文件

如果设计文档和代码实现冲突，先判断是否是已经确认过的实现调整。确需改变需求或边界时，先更新设计文档，再改代码。

## 2. 本地开发环境

推荐 Python 3.11 或 3.12。

macOS / Linux：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Windows PowerShell：

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

如果 PowerShell 禁止执行虚拟环境脚本，可以在当前窗口执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 3. 分支规范

禁止直接在 `main` 上开发。

推荐分支命名：

```text
feature/m0-project-bootstrap
feature/m1-data-model
feature/m2-crawler-static
fix/crawler-timeout
docs/update-deploy-guide
```

每个分支只做一个明确目标，不混入无关重构。

## 4. 任务推进原则

按 M0 到 M6 顺序推进：

- M0：项目底座与开发规范。
- M1：数据模型与基础后台。
- M2：抓取核心闭环。
- M3：变化检测与任务统计。
- M4：后台查询与本地归档体验。
- M5：OpenClaw 企微通知。
- M6：扩展站点与端到端验收。

除非团队确认，否则不要跨阶段开发。尤其不要在没有数据模型和配置体系前，把所有抓取逻辑继续堆到单个脚本里。

## 5. 代码组织原则

正式应用采用轻量单体，但模块边界要清楚：

```text
services/crawler      请求、解析、变化检测、附件下载的抓取核心闭环
services/notifier     OpenClaw 和后续通知适配器
services/scheduler    每日定时抓取和手动每日任务入口
services/storage      本地归档目录、快照和附件文件写入
routers/web           后台页面
routers/api           API 接口
```

禁止：

- 把抓取、解析、下载、入库、通知全部写在一个函数里。
- 在业务逻辑中硬编码本机路径。
- 在代码中写死 OpenClaw token、企微 secret、账号密码。
- 为了一个网站写破坏通用结构的特殊逻辑。

## 6. 数据模型规范

核心对象必须保持清晰：

- `users`：后台用户。
- `sites`：政府网站。
- `site_sections`：栏目。
- `crawl_runs`：抓取批次。
- `announcements`：公告或公开信息。
- `attachments`：附件。
- `change_logs`：变化记录。
- `notification_logs`：通知日志。

附件必须独立建模，不能只塞进公告 JSON 字段。变化记录必须可追溯到任务、公告和附件。

## 7. 抓取策略规范

V1 至少支持以下策略：

- `static_html`：普通静态页面。
- `enhanced_http`：增强请求头、超时、重试。
- `browser_rendered`：Playwright 渲染。
- `json_api`：公开 JSON 接口。
- `custom_adapter`：特殊网站适配器。
- `manual_import`：预留手动导入。
- `limited_note`：不可抓或不适合抓时写入说明型结果。

对不可抓、无历史时间、HTTP 521、当前状态库等情况，不要简单标为程序失败。应记录清晰的业务原因，保证整批任务可继续完成。

外部网站抓取代码必须遵守：

- 默认设置超时和重试，不允许无限等待。
- 保持低频请求，不做高频并发压测。
- 列表页、详情页、附件下载失败时要记录失败 URL 和原因。
- 新增网站优先通过配置解决；只有配置无法表达时才新增专用适配逻辑。

## 8. 文件与路径规范

必须兼容 Windows：

- 使用 `pathlib` 拼接路径。
- 文件名清理 Windows 非法字符：`<>:"/\\|?*` 和控制字符。
- 数据库存储相对路径，不存储某台电脑的绝对路径。
- 后台下载文件必须通过接口，不直接暴露本机绝对路径。
- `storage` 根目录必须可配置。

禁止提交：

- `storage/` 真实归档文件。
- `data/*.db` 本地数据库。
- `.env` 真实配置。
- 企微或 OpenClaw 密钥。
- 客户数据和内部群 chatid。

## 9. 前端规范

V1 后台是内部工作台，不做营销页。

必须遵守：

- 第一屏展示实际工作台，不做介绍型首页。
- 信息密度适中，适合高频查看。
- 状态颜色语义一致：成功绿色、警告橙色、失败红色、变化紫色、附件青色。
- 不使用大面积渐变、装饰性光斑和无意义插画。
- 表格标题、按钮、标签不能在常见宽度下溢出。
- 页面入口必须覆盖：工作台、抓取信息、附件管理、抓取任务、网站栏目、通知日志、系统配置。

视觉细节参考：

- `docs/建筑资质公开信息监测与归档系统_前端UI详细设计.md`
- `docs/assets/建筑资质公开信息监测与归档系统_工作台Demo.png`

## 10. 测试规范

每个功能完成必须补充与风险匹配的测试。

最低要求：

- 配置读取有测试。
- 路径和文件名清理有测试。
- 公告唯一键生成有测试。
- 新增检测、正文 hash 检测、附件 hash 检测有测试。
- 至少 1 个静态 HTML 解析 fixture。
- 至少 1 个 JSON API 解析 fixture。
- 通知失败不影响任务完成的测试。
- 定时任务只抓取启用网站和启用栏目的测试。

抓取外部网站的测试不要依赖实时网络。应使用 fixture、mock 或录制样例，避免测试不稳定。

## 11. 数据库迁移规范

涉及表结构变化时必须新增 Alembic migration，不允许只改 SQLAlchemy model。

迁移要求：

- migration 文件名能看出变更意图。
- upgrade 和 downgrade 都要可执行。
- 本地执行 `alembic upgrade head` 通过。
- PR 或提交说明中写清是否新增配置项、是否需要迁移。

## 12. 提交前检查

提交或合并前至少执行：

```bash
pytest
ruff check .
ruff format --check .
```

如果 M0 阶段尚未引入这些工具，则任务完成时必须补充对应命令，并更新本文件。

涉及数据库迁移时还需要执行：

```bash
alembic upgrade head
```

涉及前端页面时，需要人工打开页面检查：

- 文字不溢出。
- 状态标签语义正确。
- 空状态、失败状态、加载状态存在。
- 附件下载和原始地址跳转入口清晰。

## 13. 提交信息规范

推荐格式：

```text
feat: add site section management
fix: handle attachment filename collision
docs: update Windows setup guide
test: cover content hash change detection
```

提交信息应说明本次改动的行为结果，而不是只写“update”。

## 14. PR / 合并说明

每次合并前说明：

- 做了什么。
- 影响哪些模块。
- 如何验证。
- 是否修改数据库迁移。
- 是否新增配置项。
- 是否影响 Windows 运行。
- 是否有未解决风险。

建议 PR 描述模板：

```markdown
## 变更内容

## 验证方式

## 配置 / 迁移

## Windows 兼容

## 风险与后续
```

## 15. 安全与合规

本系统只抓取公开政府网站信息，不做验证码绕过、登录绕过、高频对抗式反爬。

开发时必须：

- 控制请求频率。
- 尊重目标站点稳定性。
- 记录抓取失败原因。
- 不主动采集与资质公告无关的个人敏感信息。
- 不把内部配置和密钥提交到仓库。

## 16. 完成定义

一个任务只有同时满足以下条件才算完成：

- 功能实现。
- 数据库迁移或配置同步完成。
- 测试通过。
- 关键异常状态已处理。
- 后台可见或日志可追踪。
- 文档已更新。
- 对照设计文档验收条件自检通过。

只写完代码但没有验证，不算完成。

MVP 阶段的功能完成还需要满足：

- 新电脑按 README 可以启动。
- 已导入的真实栏目至少能完成一次手动抓取验证。
- 后台能看到抓取结果、失败原因、附件下载入口和通知日志。
- OpenClaw 未配置、发送失败、发送成功三种状态至少有测试或人工验证记录。
- Windows 兼容风险已检查：路径、文件名、环境变量、SQLite 路径都不依赖某台机器。
