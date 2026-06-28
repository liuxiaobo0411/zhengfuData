# Windows 实机验收记录模板

本模板用于在目标 Windows 电脑上记录建筑资质公开信息监测与归档系统的安装、运行、抓取、通知和附件下载验收结果。

## 基本信息

| 项目 | 记录 |
| --- | --- |
| 验收日期 |  |
| 验收人 |  |
| Windows 版本 |  |
| Python 版本 |  |
| 部署包来源 | GitHub Actions artifact：`zhengfudata-windows-deployment` / 本地导出 |
| 部署目录 |  |
| OpenClaw 通知模式 | webhook / cli / 未配置 |
| 企微群通知目标 |  |

## 部署包确认

| 检查项 | 命令或位置 | 结果 | 备注 |
| --- | --- | --- | --- |
| 部署包可解压 | 右键解压或 `Expand-Archive` | 通过 / 不通过 |  |
| 包内存在 `.env.example` | 解压目录 | 通过 / 不通过 |  |
| 包内不存在 `.env` | 解压目录 | 通过 / 不通过 |  |
| 包内不存在 `data` | 解压目录 | 通过 / 不通过 |  |
| 包内不存在 `storage` | 解压目录 | 通过 / 不通过 |  |
| manifest 存在 | `DEPLOYMENT_PACKAGE_MANIFEST.txt` | 通过 / 不通过 |  |

可选自动验证：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
scripts\windows\verify-deployment-package.ps1 -PackagePath <部署包.zip> -PythonCommand python
```

执行结果：

```text

```

## 初始化验收

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
scripts\windows\setup.ps1 -PythonCommand python
```

| 检查项 | 结果 | 备注 |
| --- | --- | --- |
| `.venv` 创建成功 | 通过 / 不通过 |  |
| 依赖安装成功 | 通过 / 不通过 |  |
| `.env` 已生成 | 通过 / 不通过 |  |
| 数据库迁移成功 | 通过 / 不通过 |  |
| 首批站点导入成功 | 通过 / 不通过 |  |

执行结果：

```text

```

## 配置确认

| 配置项 | 当前值或状态 | 结果 |
| --- | --- | --- |
| `APP_SECRET_KEY` 已修改 |  | 通过 / 不通过 |
| `ADMIN_PASSWORD` 已修改 |  | 通过 / 不通过 |
| `APP_PUBLIC_BASE_URL` |  | 通过 / 不通过 |
| `OPENCLAW_NOTIFY_MODE` |  | 通过 / 不通过 |
| `OPENCLAW_WEBHOOK_URL` 或 `WECOM_NOTIFY_TARGET_ID` |  | 通过 / 不通过 |
| `APP_STORAGE_ROOT` |  | 通过 / 不通过 |

## 系统自检

```powershell
scripts\windows\doctor.ps1
```

期望：无 `FAIL`。

执行结果：

```text

```

## 本机交付验收

快速验收：

```powershell
scripts\windows\run-local-acceptance.ps1 -SkipSourceValidation -SkipDailyCrawl -SkipV2
```

完整抽样验收：

```powershell
scripts\windows\run-local-acceptance.ps1 -SourceLimit 2 -DailyLimit 2
```

执行结果：

```text

```

验收报告路径：

```text
storage\exports\
```

## 来源和抓取验收

来源抽样验证：

```powershell
scripts\windows\validate-sources.ps1 -Limit 2
```

每日抓取抽样：

```powershell
scripts\windows\run-daily-crawl.ps1 -Limit 2
```

| 检查项 | 结果 | 备注 |
| --- | --- | --- |
| 来源抽样验证成功 | 通过 / 不通过 |  |
| 每日抓取抽样成功 | 通过 / 不通过 |  |
| 后台抓取任务可查看 | 通过 / 不通过 |  |
| 公告列表有新增或历史数据 | 通过 / 不通过 |  |
| 附件可下载 | 通过 / 不通过 |  |

执行结果：

```text

```

## 后台页面验收

启动后台：

```powershell
scripts\windows\run-server.ps1
```

访问地址：

```text
http://127.0.0.1:8000/
```

| 页面 | 结果 | 备注 |
| --- | --- | --- |
| 登录页 | 通过 / 不通过 |  |
| 工作台 | 通过 / 不通过 |  |
| 抓取信息 | 通过 / 不通过 |  |
| 附件管理 | 通过 / 不通过 |  |
| 变化记录 | 通过 / 不通过 |  |
| 抓取任务 | 通过 / 不通过 |  |
| 通知日志 | 通过 / 不通过 |  |
| 网站栏目 | 通过 / 不通过 |  |
| 系统配置 | 通过 / 不通过 |  |
| 知识库检索 | 通过 / 不通过 |  |

## OpenClaw / 企微通知验收

发送日报：

```powershell
.venv\Scripts\python.exe -m app.cli send-daily-report
```

| 检查项 | 结果 | 备注 |
| --- | --- | --- |
| 命令执行成功 | 通过 / 不通过 |  |
| 通知日志记录 success | 通过 / 不通过 |  |
| 企微群收到日报 | 通过 / 不通过 |  |

执行结果：

```text

```

## V2 知识库验收

```powershell
scripts\windows\v2-acceptance-check.ps1
```

执行结果：

```text

```

## 问题记录

| 编号 | 问题描述 | 复现步骤 | 临时处理 | 后续动作 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  | 待处理 / 已解决 |

## 最终结论

| 结论项 | 结果 |
| --- | --- |
| Windows 实机安装 | 通过 / 不通过 |
| 本机交付验收 | 通过 / 不通过 |
| 抓取抽样 | 通过 / 不通过 |
| 后台页面 | 通过 / 不通过 |
| 附件下载 | 通过 / 不通过 |
| OpenClaw / 企微通知 | 通过 / 不通过 / 未配置 |
| V2 知识库 | 通过 / 不通过 |

最终结论：

```text

```
