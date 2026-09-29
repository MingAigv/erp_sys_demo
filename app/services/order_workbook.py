from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.errors import BusinessError


# Keep source field names beside Chinese labels so relations remain unambiguous.
LABELS = {
    'id': '数据库ID', 'shop_id': '店铺ID', 'platform_order_id': '平台订单号',
    'status': '状态', 'currency': '币种', 'subtotal': '商品小计',
    'buyer_shipping_amount': '买家运费', 'tax_amount': '税额',
    'discount_amount': '折扣', 'total_amount': '订单总额',
    'ordered_at': '下单时间', 'platform_updated_at': '平台更新时间',
    'receiver_name': '收件人', 'receiver_company': '收件公司',
    'receiver_country': '国家', 'receiver_address1': '地址1',
    'receiver_address2': '地址2', 'receiver_city': '城市',
    'receiver_state': '省州', 'receiver_zip': '邮编', 'receiver_phone': '电话',
    'receiver_phone_ext': '分机', 'internal_notes': '内部备注',
    'source': '数据来源', 'is_mock': '模拟数据', 'order_id': '订单ID',
    'platform_item_id': '平台商品ID', 'title': '商品名称', 'sku': 'SKU',
    'quantity': '数量', 'unit_price': '商品单价', 'unit_weight': '商品单位重量',
    'country_of_origin': '原产国', 'package_reference': '包裹业务编号',
    'carrier': '承运商', 'tracking_number': '物流单号', 'shipping_date': '发货日期',
    'weight': '重量', 'length': '长', 'width': '宽', 'height': '高',
    'measurement_unit': '重量尺寸单位', 'additional_insurance': '附加保险',
    'insurance_value': '保险金额', 'shipment_purpose': '寄件用途',
    'shipping_notes': '发货备注', 'email_label_to': '面单邮箱',
    'address_translation_1': '地址翻译1', 'address_translation_2': '地址翻译2',
    'notes_on_invoice': '发票备注', 'danger_goods': '危险品标记',
    'shipment_id': '包裹ID', 'order_item_id': '商品明细ID',
    'source_transaction_id': '来源流水号', 'type': '流水类型',
    'amount': '金额', 'occurred_at': '发生时间', 'description': '说明',
    'platform_shop_id': '平台店铺号', 'name': '店铺名称',
}
MEASURES = {'weight', 'length', 'width', 'height', 'unit_weight'}
XLSX_MAX_ROWS = 1_048_576


def write_value(cell, value, field, sheet_name, record_id):
    """Preserve identifiers/formula-like text and avoid Excel numeric precision loss."""
    if isinstance(value, datetime):
        value = value.astimezone(timezone.utc).isoformat()
    elif isinstance(value, date):
        value = value.isoformat()
    elif isinstance(value, Decimal):
        precision = '.3f' if field in MEASURES else '.2f'
        # Excel supports only 15 significant decimal digits. Large values stay exact text.
        if len(value.normalize().as_tuple().digits) > 15 or abs(value) >= Decimal('1e15'):
            value = format(value, precision)
        else:
            cell.number_format = '0.000' if field in MEASURES else '0.00'
    elif isinstance(value, int) and not isinstance(value, bool) and abs(value) >= 10**15:
        value = str(value)
    if isinstance(value, str):
        if len(value) > 32767 or ILLEGAL_CHARACTERS_RE.search(value) or any(
            0xD800 <= ord(char) <= 0xDFFF or ord(char) in (0xFFFE, 0xFFFF)
            for char in value
        ):
            raise BusinessError('INVALID_EXPORT_TEXT', '文本无法无损写入 Excel，请修正后重试', [
                {'sheet': sheet_name, 'record_id': record_id, 'field': field,
                 'reason': '包含 XLSX 不支持的字符或超过单元格长度上限'}
            ])
        cell.value = value
        cell.data_type = 's'
        cell.number_format = '@'
    else:
        cell.value = value


def add_sheet(book, name, fields, records):
    sheet = book.create_sheet(name)
    sheet.append([f'{LABELS.get(field, field)} ({field})' for field in fields])
    sheet.freeze_panes = 'A2'
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='234E70')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
        sheet.column_dimensions[get_column_letter(cell.column)].width = 26
    sheet.row_dimensions[1].height = 32
    count = 0
    for row_index, record in enumerate(records, start=2):
        if row_index > XLSX_MAX_ROWS:
            raise BusinessError('EXPORT_TOO_LARGE', f'{name}超过 Excel 单表行数上限，请按 ID 分批导出')
        for column, field in enumerate(fields, start=1):
            write_value(sheet.cell(row_index, column), getattr(record, field), field,
                        name, getattr(record, 'id', None))
        count += 1
    sheet.auto_filter.ref = f'A1:{get_column_letter(len(fields))}{count + 1}'
    return count


def build_workbook(tables, all_orders):
    book = Workbook()
    book.remove(book.active)
    counts = []
    for name, fields, records in tables:
        counts.append((name, add_sheet(book, name, fields, records)))
    notes = book.create_sheet('导出说明')
    for row in [
        ('项目', '说明'),
        ('导出范围', '全部订单及全部财务流水、店铺' if all_orders else '指定订单及其关联数据'),
        ('生成时间 UTC', datetime.now(timezone.utc).isoformat()),
        ('文件用途', '内部查询与统计，不是 PostPony 导入模板；不会获取 Etsy 最新数据。'),
        ('缺失值', '缺失字段保留为空；多商品、多包裹完整保留。'),
        ('数据关联', '订单.shop_id → 店铺.id；商品/包裹/流水.order_id → 订单.id；装箱明细使用包裹ID和商品明细ID关联。'),
        ('金额与币种', '流水自带币种；商品单价沿用订单币种；不要跨币种相加。重量和尺寸按包裹记录的单位解释。'),
        ('财务口径', '全量包含 order_id 为空的店铺流水；按 ID 导出不含未关联流水。提现不等于订单收入，费用不做分摊。'),
        ('精度与文本', '订单号、物流号、邮编等保留为文本；超出 Excel 安全精度的数值也按文本保留。时间含 UTC 时区。'),
        ('重复计数', '订单、商品、包裹和财务分别一条记录一行，通过 ID 关联；不要连接后重复加总订单金额。'),
        *[(f'{name}记录数', count) for name, count in counts],
    ]:
        notes.append(row)
    notes.column_dimensions['A'].width = 24
    notes.column_dimensions['B'].width = 95
    notes.freeze_panes = 'A2'
    for row in notes:
        row[1].alignment = Alignment(wrap_text=True, vertical='top')
        notes.row_dimensions[row[0].row].height = 42
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()
