# 实际验证记录

## 2026-09-29：普通订单 Excel 导出

- 新增 `GET /api/v1/exports/orders` 全量导出和 `POST /api/v1/exports/orders` 指定 ID 导出；不依赖模板，原有 PostPony 接口保留。
- `python -m compileall -q app tests` 与 `git diff --check` 通过。
- 固定数据／SQLite portable 测试：10 项通过。
- 使用现有 bundled Python 的 openpyxl 执行 `python -m unittest discover -s tests -p '*workbook_portable.py' -v`：8 项通过，其中新增 5 项普通导出生产写出代码测试，原有 3 项 PostPony 写出测试。
- 新增测试实际将 XLSX 写入内存并回读，检查前导零、长物流号、公式形式文本、普通数值与超精度金额、UTC 日期、缺失值、空表、文本校验、Excel 行数上限及连续导出隔离。
- `tests/test_order_export.py` 已补充 HTTP 集成测试，覆盖全量记录数、无模板导出、指定 ID 及关系过滤、重复 ID、不存在 ID、非法请求、空库、金额和币种、错误定位、原接口回归、Swagger 下载声明。
- 本次环境缺 FastAPI、SQLAlchemy、Alembic、pytest 等依赖；安装依赖的权限请求被拒绝。实际运行 `.venv/Scripts/python.exe -m pytest -q` 返回 `No module named pytest`，因此未验证 HTTP 集成测试，不宣称完整测试通过。
- 在依赖完整的服务器上执行 `python -m pytest -q` 后，再通过 `/docs` 下载全量及指定 ID 文件完成接口验收。

## 初始版本验证

验证日期：2026-09-28。环境：Windows PowerShell，系统 Python 3.13.5。

## 已执行

- `python -m compileall -q app migrations scripts tests`：Python 语法编译检查。
- `python -m unittest discover -s tests -p test_portable.py -v`：**10 项通过**。使用内存 SQLite，执行真实冻结迁移 DDL 与触发器，覆盖固定 fixture 一致性、2 店 50 单及 106 笔流水、金额符号／总额、装箱数量、跨订单约束、直接修改父记录、跨店财务、前导零及长编号、唯一键、外键、DDL 重建。
- 使用应用自带的 Python（已有 openpyxl）运行 `python -m unittest discover -s tests -p test_workbook_portable.py -v`：**3 项通过**。调用实际生产 workbook 写出／回读代码，覆盖 33 列结构、文本／数值类型、公式文本、样式／批注／列宽、下拉范围扩展、辅助表保留、示例清除、缺模板错误及回读发现公式篡改。

这 13 项不是 FastAPI 集成测试；Excel 测试使用内存中的合成测试模板，不是原始 PostPony 文件。

## 未能执行与原因

- 系统 Python 缺 FastAPI、SQLAlchemy、Alembic、openpyxl、pytest、httpx、pydantic-settings。
- 应用自带 Python 有 openpyxl，但仍缺 FastAPI、SQLAlchemy、Alembic、pytest、httpx、pydantic-settings。
- 创建 `.venv` 时 ensurepip 被临时目录权限阻止；权限提升请求被拒绝。
- 尝试安装 requirements.txt 时当前环境未能取得依赖包，安装权限提升请求被拒绝。
- 实际执行 `python -m pytest -q` 返回 `No module named pytest`，未进入集成测试收集阶段。
- 因此未声明依赖版本组合已运行通过，也未运行完整 pytest、真实 Alembic 命令、Swagger 服务、HTTP 同步／查询／下载闭环。`tests/test_business.py`、`tests/test_export.py` 和 conftest 已提供，待安装后运行。
- 本次没有 XLSX 原模板，未验证实际表头／批注／Remarks／Data table；未连接真实 PostPony，不声称通过平台导入。

## 待完成验收

1. 在允许安装依赖的环境运行 README 安装命令及 `python -m pytest -q`，修复实际发现的问题。
2. 提供真实模板，运行 `python -m app.cli inspect-template`；记录文件哈希并逐项核对文档中的待确认规则。
3. 执行迁移 → 显式模拟同步 → 查询 → 预览 → 下载流程；检查重复同步保持 50 个订单、106 笔流水。
4. 对生成文件进行 PostPony 测试导入并记录结果，再决定是否启用任何多行布局策略。
