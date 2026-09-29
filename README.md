# Etsy 本地订单管理与 PostPony 模板导出

Python 3.11+、FastAPI、SQLAlchemy 2.x、Pydantic 2.x、SQLite、Alembic、openpyxl 的同步后端。仅使用固定模拟数据，无前端、无 Etsy API、无爬虫、无物流服务连接。默认只在 `127.0.0.1` 运行。

**交付状态：代码、迁移、50 单固定数据及测试已创建。附件未包含真实 Excel 模板，因此尚未核对其批注、Remarks、下拉内容，也未进行真实 PostPony 导入。没有自动生成冒充原模板的文件。当前环境完整依赖安装受限，实际完成的验证见 [验证记录](docs/verification.md)。**

## 目录

```text
app/
  api/routes.py                 HTTP 参数、路由
  schemas/__init__.py           Pydantic 请求、分页、预览响应
  models/__init__.py            七类实体与模拟数据标记
  providers/__init__.py         DataProvider / MockDataProvider
  services/
    sync.py                    幂等同步、审计、事务
    queries.py                 查询、详情、财务摘要
    packing.py                 商品装箱业务约束
    mapping.py                 独立 33 列映射
    export.py                  导出策略和统一校验
    workbook.py                模板读取、写出及回读验证
  config.py / db.py / main.py / cli.py
fixtures/mock.json              固定 2 店、50 单、106 笔流水
fixtures/non_usd.json           独立非 USD 拒绝测试数据
templates/                     放置真实原模板
migrations/                    Alembic 迁移与冻结的初始 SQLite DDL
tests/                         pytest 集成测试及可独立运行的检查
scripts/build_fixtures.py       确定性 fixture 构建工具，不在启动时执行
scripts/demo.ps1               已启动服务的查询—预览—下载演示
docs/                          映射、规则、验证记录
requirements.txt / .env.example / alembic.ini
```

## Windows PowerShell 安装、迁移、初始化与启动

在项目根目录执行（本次位置为 `D:\自媒体`）：

```powershell
Set-Location 'D:\自媒体'
python --version   # 要求 3.11+
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

无需激活虚拟环境，也无需修改 PowerShell 执行策略。若 `.venv` 已存在但创建未完成，可再次执行 `python -m venv .venv` 修复；本次环境的 `ensurepip` 临时目录权限阻止了初始化，需要在允许安装的本机环境完成。

将原始 Excel 复制到 `templates\postpony.xlsx`；或者在 `.env` 中设置绝对路径。示例：

```dotenv
DATABASE_PATH=./data/etsy.sqlite3
POSTPONY_TEMPLATE=./templates/postpony.xlsx
EXPORT_ORDER_ID_MAX_LENGTH=30
EXPORT_ADDRESS_MAX_LENGTH=35
```

相对路径以启动进程的当前工作目录为基准，请始终从项目根目录执行命令。原模板仅被读取；不要将导出目标路径设为原模板路径。

```powershell
# 1. 显式迁移；创建数据库表和约束
.\.venv\Scripts\python.exe -m alembic upgrade head

# 2. 显式同步固定模拟数据（第二次同步应为 0 新增 / 0 更新 / 50 未变化）
.\.venv\Scripts\python.exe -m app.cli sync-mock

# 可选：原模板到位后查看真实表头、批注、颜色、校验、辅助页
.\.venv\Scripts\python.exe -m app.cli inspect-template

# 3. 启动；默认演示命令只监听本机
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Swagger：<http://127.0.0.1:8000/docs>。OpenAPI：<http://127.0.0.1:8000/openapi.json>。

启动只建立配置和连接工厂，不创建表、不同步、不清空数据库。第一次请求未迁移数据库会返回明确的数据库错误。`/api/v1/health` 同时检查数据库连接和 Alembic 版本记录。

## 普通 Excel 导出（无需模板）

普通导出用于内部查看、统计，支持多商品、多包裹、非 USD 和缺少发货必填字段的订单。
它不受 PostPony 的模板及必填校验限制，也不连接 Etsy 获取最新订单。
原有 `/api/v1/exports/postpony/preview` 和 `/api/v1/exports/postpony` 保持原有行为。

| 接口 | 用途 | 请求 |
| --- | --- | --- |
| `GET /api/v1/exports/orders` | 导出数据库中全部订单及明细，无分页限制 | 无请求体 |
| `POST /api/v1/exports/orders` | 按数据库订单 ID 导出 | `{"order_ids":[1,2,3]}` |

指定 ID 时最多 500 项、重复 ID 去重；空列表、非整数、非正整数和未知参数返回 422。
有不存在的 ID 时整批返回 `ORDERS_NOT_FOUND`，不悄悄忽略。全部导出必须使用 GET 接口，空请求不代表全部。
空数据库也会生成带表头的工作簿。各表按数据库 ID 稳定排序。

工作簿包含：**订单、商品、包裹、装箱明细、财务流水、店铺、导出说明**。
每种实体一条记录一行，保留所有数据库字段，以 ID 关联，避免多商品和多包裹导致金额重复。
全量导出包含全部店铺，以及没有关联订单的店铺费用、提现；按 ID 导出仅包含所选订单的关联流水和所属店铺。
金额必须按币种分别统计，提现不算订单收入。缺失值为空，不自动补齐。
订单号、物流单号、邮编等保持文本，公式形式的文本不会作为公式执行；时间为含 UTC 时区的文本。
正常金额、重量和数量是数值；超过 Excel 安全精度的值以文本保存，避免丢失精度。
超长或不支持的文本返回 `INVALID_EXPORT_TEXT` 并定位字段，不截断；单表超出 Excel 行数上限返回 `EXPORT_TOO_LARGE`。
当前在内存中构建工作簿，适合演示和小规模内部使用，大数据量应按 ID 分批导出。

在 Swagger `/docs` 中找到上述接口，点击 **Try it out → Execute → Download file**。
也可以直接访问 `/api/v1/exports/orders` 下载全部数据。

Linux 服务器上执行（文件保存在服务器当前目录）：

```bash
# 全部订单；无需 PostPony 模板
curl --fail-with-body 'http://127.0.0.1:8000/api/v1/exports/orders' -o all-orders.xlsx

# 指定订单，包括多商品和多包裹的订单
curl --fail-with-body -X POST 'http://127.0.0.1:8000/api/v1/exports/orders' \
  -H 'Content-Type: application/json' \
  -d '{"order_ids":[1,2,3]}' -o selected-orders.xlsx
```

curl 报错时输出文件可能是 JSON 错误，不应当作 XLSX 使用。
更新代码后需重启 Uvicorn 才能看到新接口，无需新增迁移或重新导入模拟数据。

## HTTP 闭环

另开 PowerShell，在项目目录执行：

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
Invoke-RestMethod "$api/health"
Invoke-RestMethod -Method Post "$api/sync/mock"
Invoke-RestMethod "$api/shops"

# 精确匹配；两个店铺都有 0001001，不删除前导零
Invoke-RestMethod "$api/orders?order_number=0001001"
Invoke-RestMethod "$api/orders?shop_id=1&order_number=0001001"
Invoke-RestMethod "$api/orders?tracking_number=00001234567890123456789012345678901234567890"
Invoke-RestMethod "$api/orders?sku=SKU-COMMON"
Invoke-RestMethod "$api/orders/5"

# 日期带时区，左闭右开：[date_from, date_to)
Invoke-RestMethod "$api/orders?date_from=2026-01-01T00%3A00%3A00Z&date_to=2026-02-01T00%3A00%3A00Z&page=1&page_size=20"

$lookup = @{ lookup_type='order_number'; values=@('0001001','missing','0001005') } | ConvertTo-Json
Invoke-RestMethod -Method Post "$api/orders/batch-lookup" -ContentType 'application/json' -Body $lookup

Invoke-RestMethod "$api/financial-transactions?shop_id=1&type=refund&currency=USD"
Invoke-RestMethod "$api/sync-runs?page=1&page_size=20"

# 选定具体订单；请使用查询返回的 id，不将平台订单号当成数据库 id
$result = Invoke-RestMethod "$api/orders?shop_id=1&order_number=0001001"
$payload = @{ order_ids=@($result.items[0].id) } | ConvertTo-Json

# 4. 预览：真实模板未提供时返回 TEMPLATE_NOT_FOUND
Invoke-RestMethod -Method Post "$api/exports/postpony/preview" -ContentType 'application/json' -Body $payload

# 5. 下载：重新运行与预览相同的严格校验
Invoke-WebRequest -Method Post "$api/exports/postpony" -ContentType 'application/json' -Body $payload -OutFile '.\postpony-orders.xlsx'
```

也可运行 `powershell -File .\scripts\demo.ps1`，它将检查健康状态、显式同步、查询一个正常订单、预览并下载。没有原模板时脚本会停在预览错误处，不创建替代格式。只有真实模板到位且依赖安装完成后，才能完成此闭环的现场验证。

## 接口行为

全部业务路由在 `/api/v1` 下。列表接口 `page >= 1`，`1 <= page_size <= 100`，默认 20；订单按 UTC 下单时间倒序、数据库 id 倒序稳定排序。日期必须提供时区，开始时间必须早于结束时间。结束时间不包含在结果中。

`GET /orders` 支持 `shop_id`、`order_number`、`tracking_number`、`sku`、`status`、`date_from`、`date_to`。订单号、物流单号、SKU 都精确匹配；商品和包裹采用 EXISTS 条件，不因关联数量扩大订单行数或 total。

`POST /orders/batch-lookup` 最多 500 个字符串，按输入顺序逐项返回 `input_value`、`status`、`orders`。去掉首尾空白，保留前导零及符号；重复输入也逐项返回。多匹配是 `ambiguous`，不会只选第一条。

`GET /orders/{id}` 返回商品、包裹和各包裹 `allocations`、关联流水、按币种分组的独立财务摘要。`net_receipts = payment + refund + fee + adjustment`，排除 payout。所有摘要金额来自关联流水，不跨币种相加，不分摊店铺级费用。金额和重量／尺寸在 API 中均返回十进制字符串。

`GET /financial-transactions` 支持 `shop_id`、`order_id`、`type`、`currency`、`date_from`、`date_to` 和分页。未指定订单时会包括 `order_id=null` 的店铺费用／提现。

导出请求 `{"order_ids":[1]}` 不接受空列表、布尔值、字符串 id 或默认全部订单，最多 500 项；重复 id 去重。任一阻断错误导致整批 422，不跳过错误订单。预览的错误响应还包含 `estimated_rows=0`、warnings、selected_orders；成功预览包含预计行数。不存在的单资源返回 404；导出批次中的不存在 id 作为整批 422 校验错误逐项定位。

统一错误主体：

```json
{
  "code": "EXPORT_VALIDATION_FAILED",
  "message": "部分订单不满足导出要求",
  "details": [{"order_id": 7, "field": "ReceiverPhone", "reason": "必填字段为空", "code": "REQUIRED_FIELD"}]
}
```

请求错误不回显完整请求体；数据库错误不回显 SQL、地址、电话。没有清空数据库接口。

## 固定场景与同步

JSON 中业务编号、日期、金额固定，无随机数。数据库内部自增 id 只在新建空库中与下表对应；稳定业务键是平台店铺号、店铺＋平台订单号、商品平台编号、包裹业务编号、店铺＋来源流水号。

| 新库订单 id | 场景 |
| --- | --- |
| 1 | 正常单商品单包裹，`0001001`、`01234`、超长物流单号 |
| 2 | 两商品一包裹；两个商品具有共同 SKU |
| 3 | 一商品购买两件，分别分配到两个稳定包裹 |
| 4 | 未发货，无物流单号、无发货日期；导出日期缺失错误 |
| 5 | 收款 27.00、部分退款 -5.00、费用 -2.00，净收款 20.00 |
| 6 | 收款 27.00、全额退款 -27.00、费用 -2.00，净收款 -2.00 |
| 7 / 8 / 9 | 分别缺电话、地址、包裹重量 |
| 26 | 第二家店同号 `0001001`，未限定店铺的查询产生多匹配 |

订单 2、3 共用查询物流值 `SHARED-TRACKING`。另有每店一笔 -10.00 店铺费用、一笔 -100.00 提现，均不绑定订单。所有实体包括包裹分配和同步记录都有 `source=mock`、`is_mock=true`。姓名和地址虚构，邮箱使用 example.com；电话是 fixture 明确填写的虚构号码，不是模板默认值。

同步用唯一键 upsert，SQLite `BEGIN IMMEDIATE` 串行化写入，锁等待 15 秒；每个同步批次采用原子数据事务并记录 SyncRun。新增、更新、未变化按订单统计，关联平台商品／流水变化也记作订单更新。店铺级流水只 upsert，不计作订单数。批次失败时数据全部回滚，failed 为本批未提交的订单数量；provider 尚未成功载入时为 0，status 仍是 failed。开始／结束时间记录真实同步运行时间，订单业务时间固定。

平台字段同步不覆盖 `internal_notes`；已存在包裹的物流、尺寸、日期及人工装箱分配全部保留，新包裹才从 provider 初始化。已存在商品数量变化仍必须满足装箱约束，不强行修改包裹。未来的删除／取消明细需要显式映射规则，本版不会因一次 provider 缺行删除本地历史。

装箱服务及 SQLite 触发器共同阻止超量、跨订单、非正整数；直接更新商品购买数量或移动已装箱实体也受触发器约束。财务流水不能绑定其他店铺的订单。资金收入为正，refund/fee/payout 为负，adjustment 可正可负。

金额使用 Decimal 运算和整数分存储；拒绝 float 输入及超过两位小数，不做静默四舍五入。重量／尺寸采用 0.001 精度，保存规范十进制文本，拒绝额外小数精度；与金额存储完全分开。UTC 以固定宽度 ISO 文本存储，API 明确含时区。数据库开启外键。

## PostPony 导出范围与后续扩展

详见 [33 列字段映射](docs/template-mapping.md) 和 [规则来源、冲突与扩展步骤](docs/template-rules.md)。

当前策略只允许一个商品行、一个包裹、完整数量分配。多商品／多包裹数据库和查询完整支持，但导出返回 `UNSUPPORTED_TEMPLATE_LAYOUT`。没有丢商品、拼接商品名或笛卡尔积；没有为猜测的平台续行规则编造实现。

USD 金额列只接收 USD；不做汇率换算。Shipping(USD) 是买家运费。所有文本按真正的文本单元格写出，`= + - @` 开头不增加前置字符，公式形式的内容不会成为公式。内存中独立创建每次导出，保留三个工作表、表头样式、列宽、批注与下拉校验；清空数据区所有示例值。写出后回读校验结构、行数、文本和值类型。金额列不经业务代码 float 中转，回读使用 Decimal 比较，拒绝因 Excel 数值精度造成失真的输出。

真实原模板未提供前，不能声明其格式、批注和下拉保留已通过验证。测试用合成模板只证明代码处理已覆盖的特性，不证明真实平台导入兼容性。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

集成测试使用 pytest `tmp_path` 中的 SQLite 和合成测试模板，并运行真实 Alembic 迁移，不污染 `data/etsy.sqlite3`。涵盖重复同步、精确查询、歧义、装箱、财务、模板保留、公式文本、错误字段、非 USD、不可用布局、重新校验等。

可单独执行依赖较少的检查：

```powershell
python -m unittest discover -s tests -p test_portable.py -v
# 以下需要 openpyxl
python -m unittest discover -s tests -p test_workbook_portable.py -v
python -m compileall -q app migrations scripts tests
```

本次实测结果及未执行项见 [验证记录](docs/verification.md)，不把静态检查或合成模板测试算作 API 全流程验收。

## 部署边界

此版本是 localhost 演示，没有身份认证。多人内网部署前增加认证、按店铺的数据访问权限、操作审计、请求大小／频率限制、备份和 HTTPS；不要直接改为公网监听。当前不连接 Etsy 或任何物流服务，不传送订单到外部平台。SQLite 适合单机低并发，出现持续写入争用后再评估数据库升级。
