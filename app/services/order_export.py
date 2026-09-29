"""Template-free export for internal reporting, independent of PostPony rules."""
from sqlalchemy import inspect, select

from app.models import Order, OrderItem, Shipment, ShipmentItem, FinancialTransaction, Shop
from app.services.errors import BusinessError
from app.services.order_workbook import build_workbook


def export_orders(session, order_ids=None):
    """None means explicit all-orders endpoint; an ID selection must be non-empty."""
    selected = select(Order.id)
    if order_ids is not None:
        ids = sorted(set(order_ids))
        if not ids:
            raise BusinessError('INVALID_PARAMETERS', '订单 ID 列表不能为空')
        found = set(session.scalars(select(Order.id).where(Order.id.in_(ids))))
        missing = sorted(set(ids) - found)
        if missing:
            raise BusinessError('ORDERS_NOT_FOUND', '部分订单不存在，未生成文件', [
                {'order_id': value, 'field': 'order_id', 'reason': '订单不存在'}
                for value in missing
            ])
        selected = selected.where(Order.id.in_(ids))

    statements = [
        ('订单', Order, select(Order).where(Order.id.in_(selected)).order_by(Order.id)),
        ('商品', OrderItem, select(OrderItem).where(OrderItem.order_id.in_(selected)).order_by(OrderItem.id)),
        ('包裹', Shipment, select(Shipment).where(Shipment.order_id.in_(selected)).order_by(Shipment.id)),
        ('装箱明细', ShipmentItem, select(ShipmentItem).join(Shipment).where(
            Shipment.order_id.in_(selected)).order_by(ShipmentItem.shipment_id, ShipmentItem.order_item_id)),
    ]
    transactions = select(FinancialTransaction)
    shops = select(Shop)
    if order_ids is not None:
        transactions = transactions.where(FinancialTransaction.order_id.in_(selected))
        shops = shops.where(Shop.id.in_(select(Order.shop_id).where(Order.id.in_(selected))))
    statements.extend([
        ('财务流水', FinancialTransaction, transactions.order_by(FinancialTransaction.id)),
        ('店铺', Shop, shops.order_by(Shop.id)),
    ])
    tables = ((name, [column.key for column in inspect(model).column_attrs],
               session.scalars(statement)) for name, model, statement in statements)
    return build_workbook(tables, all_orders=order_ids is None)
