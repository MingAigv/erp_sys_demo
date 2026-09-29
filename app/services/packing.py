from sqlalchemy import select, func
from app.models import Shipment, OrderItem, ShipmentItem
from app.services.errors import BusinessError

def allocate(session, shipment_id: int, order_item_id: int, quantity: int):
    shipment, item = session.get(Shipment, shipment_id), session.get(OrderItem, order_item_id)
    if shipment is None or item is None:
        raise BusinessError('NOT_FOUND', '包裹或商品不存在', status=404)
    if shipment.order_id != item.order_id or isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise BusinessError('INVALID_ALLOCATION', '包裹与商品须属于同一订单且数量为正整数')
    other = session.scalar(select(func.coalesce(func.sum(ShipmentItem.quantity), 0)).where(ShipmentItem.order_item_id == order_item_id, ShipmentItem.shipment_id != shipment_id))
    if other + quantity > item.quantity:
        raise BusinessError('OVER_ALLOCATION', '装箱数量超过购买数量')
    allocation = session.get(ShipmentItem, (shipment_id, order_item_id))
    if allocation:
        allocation.quantity = quantity
    else:
        session.add(ShipmentItem(shipment_id=shipment_id, order_item_id=order_item_id, quantity=quantity))
    session.flush()
