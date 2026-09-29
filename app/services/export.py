import re
from decimal import Decimal
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from app.models import Order
from app.services.errors import BusinessError
from app.services.mapping import MAPPING, REQUIRED
from app.services.workbook import load_template, write_workbook


class SingleItemSinglePackageStrategy:
    """Conservative layout; replace only after real PostPony import verification."""
    def rows(self, order):
        if len(order.items) != 1 or len(order.shipments) != 1:
            raise BusinessError('UNSUPPORTED_TEMPLATE_LAYOUT', '多商品或多包裹的真实导入续行规则尚未确认')
        shipment, item = order.shipments[0], order.items[0]
        allocations = shipment.allocations
        if len(allocations) != 1 or allocations[0].order_item_id != item.id or allocations[0].quantity != item.quantity:
            raise BusinessError('INVALID_ALLOCATION', '导出要求购买数量完整且准确地分配到包裹')
        context = {'order': order, 'shipment': shipment, 'item': item, 'allocation': allocations[0]}
        row = {}
        for header, source, attr in MAPPING:
            row[header] = order.platform_order_id if source == 'derived' else getattr(context[source], attr)
        return [row]


def prepare(session, order_ids, settings):
    workbook = load_template(settings.postpony_template)
    errors, warnings, rows = [], [], []
    seen = {}
    def issue(target, order_id, field, reason, code='INVALID_FIELD'):
        target.append(dict(order_id=order_id, field=field, reason=reason, code=code))
    for order_id in dict.fromkeys(order_ids):
        order = session.get(Order, order_id)
        if order is None:
            issue(errors, order_id, 'order_id', '订单不存在', 'NOT_FOUND')
            continue
        if order.currency != 'USD':
            issue(errors, order_id, 'currency', '模板 USD 金额列不接受其他币种', 'UNSUPPORTED_CURRENCY')
        try:
            candidates = SingleItemSinglePackageStrategy().rows(order)
        except BusinessError as exc:
            issue(errors, order_id, 'layout', exc.message, exc.code)
            continue
        before = len(errors)
        for row in candidates:
            for field in REQUIRED:
                if row[field] is None or (isinstance(row[field], str) and not row[field].strip()):
                    issue(errors, order_id, field, '必填字段为空', 'REQUIRED_FIELD')
            for field, values in {
                'Weight Unit(Default:bls)': {'kg/cm', 'lbs/in', 'oz/in'},
                'ShipmentPurpose': {'Commercial', 'Sample', 'Personal Use', 'GIFT', '', None},
                'AdditionalInsurance': {'Y', 'N', '', None},
                'DangerGoods': {'', None, 'BATTERY_MARKED', 'BATTERY_UNMARKED'},
            }.items():
                if row[field] not in values:
                    issue(errors, order_id, field, '不支持的枚举值')
            for field in ('Weight', 'Length', 'Width', 'Height', 'ItemUnitWeight'):
                if row[field] is not None and row[field] <= 0:
                    issue(errors, order_id, field, '数值必须大于零')
            for field in ('Shipping(USD)', 'ItemUnitPrice(USD)', 'InsuranceValue'):
                if row[field] is not None and row[field] < 0:
                    issue(errors, order_id, field, '数值不得为负')
                if row[field] is not None and row[field] > Decimal('9999999999999.99'):
                    issue(errors, order_id, field, '数值超过 Excel 15 位有效数字的安全金额范围')
            if not isinstance(row['ItemQTY'], int) or row['ItemQTY'] <= 0:
                issue(errors, order_id, 'ItemQTY', '数量必须为正整数')
            for field in ('CountryOfOrigin', 'ItemUnitWeight'):
                if row[field] is None or row[field] == '':
                    issue(errors, order_id, field, '业务字段缺失，不推测补全', 'MISSING_BUSINESS_FIELD')
            export_id = row['OrderID']
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,' + str(settings.export_order_id_max_length) + '}', export_id):
                issue(errors, order_id, 'OrderID', '保守规则仅允许字母、数字、下划线、连字符，且不得超过配置长度')
            if export_id in seen:
                issue(errors, order_id, 'OrderID', '所选店铺存在重复导出编号，请分店铺导出', 'DUPLICATE_EXPORT_ID')
            seen[export_id] = order_id
            for field in ('ReceiverAddress1', 'ReceiverAddress2', 'Address Translation 1', 'Address Translation 2'):
                if row[field] and len(row[field]) > settings.export_address_max_length:
                    issue(errors, order_id, field, '地址超过可配置的保守长度；不会截断')
            for field, value in row.items():
                if isinstance(value, str) and (ILLEGAL_CHARACTERS_RE.search(value) or len(value) > 32767):
                    issue(errors, order_id, field, '文本含 XLSX 不允许的控制字符或超过单元格长度')
            if row['ReceiverCountry'] != 'US':
                issue(warnings, order_id, 'ReceiverCountry', '非 US 地址需人工验证国家及地区代码；Data table 不是权威全球字典', 'COUNTRY_REVIEW')
            issue(warnings, order_id, 'template', '真实模板批注/Remarks 和平台导入兼容性仍需核对；当前长度规则是本地保守策略', 'UNVERIFIED_TEMPLATE_RULES')
        if len(errors) == before and order.currency == 'USD':
            rows.extend(candidates)
    report = {'valid': not errors, 'estimated_rows': len(rows) if not errors else 0, 'errors': errors, 'warnings': warnings, 'selected_orders': len(set(order_ids))}
    return report, rows, workbook


def export_workbook(session, order_ids, settings):
    report, rows, workbook = prepare(session, order_ids, settings)
    if report['errors']:
        raise BusinessError('EXPORT_VALIDATION_FAILED', '部分订单不满足导出要求', report['errors'])
    return write_workbook(workbook, rows)
