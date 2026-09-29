import json
from pathlib import Path
from decimal import Decimal
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from app.models import Order, OrderItem, Shipment, ShipmentItem, FinancialTransaction
from app.services.packing import allocate
from app.services.errors import BusinessError

def test_repeat_sync_no_duplicates(seeded):
    app, client, _, _ = seeded
    result = client.post('/api/v1/sync/mock').json()
    assert (result['added'], result['updated'], result['unchanged']) == (0, 0, 50)
    assert client.get('/api/v1/orders').json()['total'] == 50
    assert client.get('/api/v1/financial-transactions').json()['total'] == 106
    with app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Order)) == 50
        assert session.scalar(select(func.count()).select_from(Shipment)) == 51
        assert session.execute(text('PRAGMA foreign_keys')).scalar() == 1
        assert session.execute(text('SELECT typeof(total_amount) FROM orders LIMIT 1')).scalar() == 'integer'

def test_queries_exact_ambiguous_and_precision(seeded):
    _, client, _, _ = seeded
    result = client.get('/api/v1/orders', params={'order_number': '0001001'}).json()
    assert result['total'] == 2
    assert client.get('/api/v1/orders', params={'order_number': '1001'}).json()['total'] == 0
    tracking = '00001234567890123456789012345678901234567890'
    rows = client.get('/api/v1/orders', params={'tracking_number': tracking}).json()
    assert rows['total'] == 1
    order = client.get('/api/v1/orders/1').json()
    assert order['shipments'][0]['tracking_number'] == tracking
    assert order['receiver_zip'] == '01234'
    assert order['ordered_at'].endswith(('+00:00', 'Z'))
    response = client.post('/api/v1/orders/batch-lookup', json={'lookup_type': 'order_number', 'values': [' 0001001 ', 'missing', '0001005']}).json()
    assert [row['status'] for row in response] == ['ambiguous', 'not_found', 'matched']
    assert response[0]['input_value'] == '0001001'
    assert len(response[0]['orders']) == 2
    scoped = client.post('/api/v1/orders/batch-lookup', json={'lookup_type': 'order_number', 'values': ['0001001'], 'shop_id': 1}).json()
    assert scoped[0]['status'] == 'matched'
    shared = client.post('/api/v1/orders/batch-lookup', json={'lookup_type': 'tracking_number', 'values': ['SHARED-TRACKING']}).json()
    assert shared[0]['status'] == 'ambiguous'
    assert len(shared[0]['orders']) == 2

def test_multi_item_multi_package_not_duplicated(seeded):
    _, client, _, _ = seeded
    assert client.get('/api/v1/orders', params={'sku': 'SKU-COMMON'}).json()['total'] == 2
    assert client.get('/api/v1/orders', params={'tracking_number': 'SHARED-TRACKING'}).json()['total'] == 2
    order = client.get('/api/v1/orders/3').json()
    assert len(order['items']) == 1 and len(order['shipments']) == 2
    assert sum(s['allocations'][0]['quantity'] for s in order['shipments']) == 2
    assert order['financial_summary']['USD']['payment'] == '47.00'

def test_allocation_service_and_database_guards(seeded):
    app, _, _, _ = seeded
    with app.state.sessions() as session:
        order = session.get(Order, 3)
        with pytest.raises(BusinessError, match=''):
            allocate(session, order.shipments[0].id, order.items[0].id, 2)
        with pytest.raises(BusinessError):
            allocate(session, order.shipments[0].id, session.get(Order, 1).items[0].id, 1)
        allocation = order.shipments[0].allocations[0]
        allocation.quantity = 2
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
        session.get(Order, 3).items[0].quantity = 1
        with pytest.raises(IntegrityError):
            session.flush()

def test_financial_summary_excludes_payout_and_shop_fee(seeded):
    app, client, _, _ = seeded
    with app.state.sessions() as session:
        tx = session.scalar(select(FinancialTransaction).where(FinancialTransaction.type == 'payout', FinancialTransaction.shop_id == 1))
        tx.order_id = 5  # Explicit test association; mock provider never infers it.
        session.commit()
    order = client.get('/api/v1/orders/5').json()
    assert order['financial_summary']['USD'] == {'payment': '27.00', 'refund': '-5.00', 'fee': '-2.00', 'adjustment': '0.00', 'payout': '-100.00', 'net_receipts': '20.00'}
    full = client.get('/api/v1/orders/6').json()['financial_summary']['USD']
    assert full['refund'] == '-27.00' and full['net_receipts'] == '-2.00'

def test_sync_preserves_manual_fields_and_counts_updates(seeded):
    app, client, _, _ = seeded
    with app.state.sessions() as session:
        order = session.get(Order, 1)
        order.internal_notes = '人工备注'
        order.receiver_name = 'Changed platform field'
        order.shipments[0].tracking_number = 'MANUAL-00001'
        order.shipments[0].weight = Decimal('1.234')
        session.commit()
    response = client.post('/api/v1/sync/mock').json()
    assert response['updated'] == 1 and response['unchanged'] == 49
    order = client.get('/api/v1/orders/1').json()
    assert order['internal_notes'] == '人工备注'
    assert order['receiver_name'] == 'Fictional Buyer 01'
    assert order['shipments'][0]['tracking_number'] == 'MANUAL-00001'
    assert Decimal(str(order['shipments'][0]['weight'])) == Decimal('1.234')

def test_date_pagination_and_errors(seeded):
    _, client, _, _ = seeded
    assert client.get('/api/v1/health').status_code == 200
    assert len(client.get('/api/v1/shops').json()) == 2
    response = client.get('/api/v1/orders', params={'date_from': '2026-01-01T12:00:00Z', 'date_to': '2026-01-02T12:00:00Z'}).json()
    assert response['total'] == 1 and response['items'][0]['id'] == 1
    assert client.get('/api/v1/orders', params={'date_from': '2026-01-01T00:00:00'}).status_code == 422
    assert client.get('/api/v1/orders', params={'page_size': 101}).status_code == 422
    assert client.get('/api/v1/orders/99999').status_code == 404
    assert client.post('/api/v1/orders/batch-lookup', json={'lookup_type': 'order_number', 'values': ['x'] * 501}).status_code == 422
    assert client.post('/api/v1/orders/batch-lookup', json={'lookup_type': 'order_number', 'values': [1001]}).status_code == 422
    first = client.get('/api/v1/orders', params={'page_size': 10, 'page': 1}).json()
    second = client.get('/api/v1/orders', params={'page_size': 10, 'page': 2}).json()
    assert not ({o['id'] for o in first['items']} & {o['id'] for o in second['items']})

def test_failed_sync_is_atomic_and_audited(seeded):
    from app.providers import MockDataProvider
    from app.services.sync import sync_mock
    from app.models import SyncRun
    app, _, _, _ = seeded
    class InvalidProvider:
        def load(self):
            data = MockDataProvider().load()
            data['orders'][0]['receiver_name'] = 'Must rollback'
            data['orders'][2]['items'][0]['quantity'] = 1
            return data
    with app.state.sessions() as session:
        with pytest.raises(BusinessError):
            sync_mock(session, InvalidProvider())
    with app.state.sessions() as session:
        assert session.get(Order, 1).receiver_name == 'Fictional Buyer 01'
        run = session.scalar(select(SyncRun).order_by(SyncRun.id.desc()))
        assert run.status == 'failed' and run.failed == 50
        assert run.added == run.updated == 0

def test_health_requires_migration(tmp_path):
    from app.main import create_app
    from app.config import Settings
    from fastapi.testclient import TestClient
    with TestClient(create_app(Settings(database_path=tmp_path / 'uninitialized.sqlite3'))) as client:
        assert client.get('/api/v1/health').status_code == 503
