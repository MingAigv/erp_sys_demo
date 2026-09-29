# PostPony 33 列映射

程序映射唯一配置位于 `app/services/mapping.py`。下表与配置对应，列名不作拼写修正。当前只启用单商品单包裹策略。

| 列 | 原样表头 | 数据来源 |
| --- | --- | --- |
| A | OrderID | 单包裹：Order.platform_order_id；未来多包裹策略：Shipment.package_reference |
| B | ReceiverName | Order.receiver_name |
| C | ReceiverCompany | Order.receiver_company |
| D | ReceiverCountry | Order.receiver_country |
| E | ReceiverAddress1 | Order.receiver_address1 |
| F | ReceiverAddress2 | Order.receiver_address2 |
| G | ReceiverCity | Order.receiver_city |
| H | ReceiverState/Province | Order.receiver_state |
| I | ReceiverZipCode | Order.receiver_zip，文本 |
| J | ReceiverPhone | Order.receiver_phone，文本 |
| K | ReceiverPhoneExt. | Order.receiver_phone_ext，文本 |
| L | Shipping(USD) | Order.buyer_shipping_amount，买家支付运费 |
| M | ShippingDate | Shipment.shipping_date，yyyy/MM/dd |
| N | AdditionalInsurance | Shipment.additional_insurance |
| O | Weight | Shipment.weight |
| P | Length | Shipment.length |
| Q | Width | Shipment.width |
| R | Height | Shipment.height |
| S | InsuranceValue | Shipment.insurance_value |
| T | ItemName | OrderItem.title |
| U | ItemSKU | OrderItem.sku，文本 |
| V | ItemUnitPrice(USD) | OrderItem.unit_price |
| W | ItemQTY | ShipmentItem.quantity，而非对每包复制订单数量 |
| X | ItemUnitWeight | OrderItem.unit_weight，按包裹所声明的重量单位解释 |
| Y | CountryOfOrigin | OrderItem.country_of_origin |
| Z | ShipmentPurpose | Shipment.shipment_purpose |
| AA | ShippingNotes | Shipment.shipping_notes |
| AB | EmailYourLabelTo | Shipment.email_label_to |
| AC | Address Translation 1 | Shipment.address_translation_1 |
| AD | Address Translation 2 | Shipment.address_translation_2 |
| AE | Weight Unit(Default:bls) | Shipment.measurement_unit，保留表头 bls 拼写 |
| AF | Notes on Invoice | Shipment.notes_on_invoice |
| AG | DangerGoods | Shipment.danger_goods |

所有非数值列强制字符串类型并使用文本格式 `@`，不增加撇号等字符。ShippingDate 为规定格式字符串。L/S/V 为金额数值，O/P/Q/R/X 为三位小数数值，W 为整数。API 和数据库内部保留 Decimal，openpyxl 接收 Decimal 写入，输出回读验证防止数值失真。原始模板中的示例值在填充前全部清空。

SKU／姓名等外部文本以 `=`、`+`、`-` 或 `@` 开头仍保存原始文本，不能变成公式。不输出 tracking_number、数据库 id、净收款或任何模板外字段。不同店铺同订单号同时导出时会出现重复 OrderID，当前明确返回 `DUPLICATE_EXPORT_ID`，可分店铺导出。
