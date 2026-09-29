from decimal import Decimal
from sqlalchemy import select, func, inspect
from app.models import Order, Shipment, OrderItem
from app.services.errors import BusinessError

def serialize(obj):
    result = {}
    for col in inspect(obj).mapper.column_attrs:
        value = getattr(obj, col.key)
        if isinstance(value, Decimal):
            precision = '.3f' if col.key in {'weight', 'length', 'width', 'height', 'unit_weight'} else '.2f'
            value = format(value, precision)
        result[col.key] = value
    return result

def date_bounds(start, end):
    for value in (start, end):
        if value is not None and value.tzinfo is None:
            raise BusinessError('INVALID_DATE', '日期时间必须包含时区，例如 2026-01-01T00:00:00Z')
    if start and end and start >= end:
        raise BusinessError('INVALID_DATE_RANGE', 'date_from 必须早于 date_to；使用左闭右开区间')

def order_query(shop_id=None, order_number=None, tracking_number=None, sku=None, status=None, date_from=None, date_to=None):
    date_bounds(date_from, date_to)
    stmt = select(Order)
    for column, value in [(Order.shop_id, shop_id), (Order.platform_order_id, order_number), (Order.status, status)]:
        if value is not None:
            stmt = stmt.where(column == value)
    if tracking_number is not None:
        stmt = stmt.where(Order.shipments.any(Shipment.tracking_number == tracking_number))
    if sku is not None:
        stmt = stmt.where(Order.items.any(OrderItem.sku == sku))
    if date_from:
        stmt = stmt.where(Order.ordered_at >= date_from)
    if date_to:
        stmt = stmt.where(Order.ordered_at < date_to)
    return stmt

def paginate(session, stmt, page, page_size, *ordering):
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.scalars(stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
    return {'total': total, 'page': page, 'page_size': page_size, 'items': [serialize(row) for row in rows]}

def get_order(session, order_id):
    order = session.get(Order, order_id)
    if order is None:
        raise BusinessError('NOT_FOUND', '订单不存在', status=404)
    return order

def detail(order):
    result = serialize(order)
    result['items'] = [serialize(i) for i in sorted(order.items, key=lambda i: i.id)]
    result['shipments'] = [{**serialize(s), 'allocations': [serialize(a) for a in s.allocations]} for s in sorted(order.shipments, key=lambda s: s.id)]
    result['financial_transactions'] = [serialize(t) for t in sorted(order.transactions, key=lambda t: t.id)]
    summaries = {}
    for tx in order.transactions:
        totals = summaries.setdefault(tx.currency, {k: Decimal('0.00') for k in ('payment', 'refund', 'fee', 'adjustment', 'payout', 'net_receipts')})
        totals[tx.type] += tx.amount
        if tx.type != 'payout':
            totals['net_receipts'] += tx.amount
    result['financial_summary'] = {currency: {key: format(value, '.2f') for key, value in totals.items()} for currency, totals in summaries.items()}
    return result
