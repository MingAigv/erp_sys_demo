from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import select, text
from app.models import Shop, Order, OrderItem, Shipment, ShipmentItem, FinancialTransaction, SyncRun
from app.providers import DataProvider
from app.services.errors import BusinessError

def normalize(data):
    result = dict(data)
    for key, value in result.items():
        if value is None:
            continue
        if key in {'ordered_at', 'platform_updated_at', 'occurred_at'}:
            result[key] = datetime.fromisoformat(value)
        elif key == 'shipping_date':
            result[key] = date.fromisoformat(value)
        elif key in {'subtotal', 'buyer_shipping_amount', 'tax_amount', 'discount_amount', 'total_amount', 'unit_price', 'unit_weight', 'weight', 'length', 'width', 'height', 'insurance_value', 'amount'}:
            result[key] = Decimal(value)
    return result

def upsert(session, model, keys, values):
    obj = session.scalar(select(model).filter_by(**keys))
    values = normalize(values)
    if obj is None:
        obj = model(**keys, **values)
        session.add(obj)
        session.flush()
        return obj, 'added'
    changed = any(getattr(obj, k) != v for k, v in values.items())
    for key, value in values.items():
        setattr(obj, key, value)
    return obj, 'updated' if changed else 'unchanged'

def sync_mock(session, provider: DataProvider):
    session.execute(text('BEGIN IMMEDIATE'))
    run = SyncRun(source='mock', status='running', started_at=datetime.now(timezone.utc))
    session.add(run)
    session.flush()
    counts = dict(added=0, updated=0, unchanged=0)
    batch_size = 0
    try:
        with session.begin_nested():
            data = provider.load()
            batch_size = len(data['orders'])
            shops = {}
            for raw in data['shops']:
                row = dict(raw)
                key = row.pop('platform_shop_id')
                shops[key], _ = upsert(session, Shop, {'platform_shop_id': key}, row)
            for raw in data['orders']:
                row = dict(raw)
                shop_id = shops[row.pop('shop')].id
                number = row.pop('platform_order_id')
                items, packages, transactions = row.pop('items'), row.pop('shipments'), row.pop('transactions')
                row.pop('internal_notes', None)
                order, state = upsert(session, Order, {'shop_id': shop_id, 'platform_order_id': number}, row)
                child_changed = False
                item_map = {}
                for raw_item in items:
                    item = dict(raw_item)
                    key = item.pop('platform_item_id')
                    item_map[key], item_state = upsert(session, OrderItem, {'order_id': order.id, 'platform_item_id': key}, item)
                    child_changed |= item_state != 'unchanged'
                for raw_package in packages:
                    package = dict(raw_package)
                    allocations = package.pop('allocations')
                    reference = package.pop('package_reference')
                    shipment = session.scalar(select(Shipment).where(Shipment.package_reference == reference))
                    if shipment is not None and shipment.order_id != order.id:
                        raise ValueError('Package reference belongs to another order')
                    if shipment is None:
                        shipment = Shipment(order_id=order.id, package_reference=reference, **normalize(package))
                        session.add(shipment)
                        session.flush()
                        for allocation in allocations:
                            session.add(ShipmentItem(shipment_id=shipment.id, order_item_id=item_map[allocation['item']].id, quantity=allocation['quantity']))
                        session.flush()
                        child_changed = True
                for raw_tx in transactions:
                    tx = dict(raw_tx)
                    key = tx.pop('source_transaction_id')
                    _, tx_state = upsert(session, FinancialTransaction, {'shop_id': shop_id, 'source_transaction_id': key}, {'order_id': order.id, **tx})
                    child_changed |= tx_state != 'unchanged'
                if state == 'unchanged' and child_changed:
                    state = 'updated'
                counts[state] += 1
            for raw_tx in data['shop_transactions']:
                tx = dict(raw_tx)
                shop_id = shops[tx.pop('shop')].id
                key = tx.pop('source_transaction_id')
                upsert(session, FinancialTransaction, {'shop_id': shop_id, 'source_transaction_id': key}, {'order_id': None, **tx})
        for key, value in counts.items():
            setattr(run, key, value)
        run.status = 'success'
    except Exception:
        run.status, run.failed = 'failed', batch_size
        run.error_summary = '同步数据校验或数据库写入失败；数据事务已回滚'
    run.finished_at = datetime.now(timezone.utc)
    session.commit()
    if run.status == 'failed':
        raise BusinessError('SYNC_FAILED', run.error_summary, [{'sync_run_id': run.id}])
    return run
