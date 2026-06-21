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
34 passed
```

## 后续验收事项

- 在 Windows 电脑按 README 完成安装、启动、导入、抓取和附件下载验证。
- 配置真实 `OPENCLAW_WEBHOOK_URL` 后，验证企微群日报发送。
- 针对待适配动态查询页面补 Playwright 或接口适配器。
- 跑一次 `zhengfudata run-daily-crawl --limit 2` 做小批量完整入库验证，再逐步扩大到 12 个启用栏目。
