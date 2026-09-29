"""Deterministic fixture authoring utility. Never invoked by startup or sync."""
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta, timezone

def build():
    data = {'shops': [{'platform_shop_id': 'MOCK-SHOP-1', 'name': 'Mock Cedar Studio', 'is_mock': True, 'source': 'mock'}, {'platform_shop_id': 'MOCK-SHOP-2', 'name': 'Mock Birch Studio', 'is_mock': True, 'source': 'mock'}], 'orders': [], 'shop_transactions': []}
    for n in range(1, 51):
        shop = 'MOCK-SHOP-1' if n <= 25 else 'MOCK-SHOP-2'
        day = datetime(2026, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=n-1)
        stamp = day.isoformat()
        number = '0001001' if n in (1, 26) else f'{1000+n:07}'
        quantity = 2 if n == 3 else 1
        items = [dict(platform_item_id=f'ITEM-{n}-1', title=f'Mock ceramic ornament {n}', sku='SKU-COMMON' if n in (2,3) else f'000SKU-{n:03}', quantity=quantity, unit_price='20.00', unit_weight='0.250', country_of_origin='US', source='mock', is_mock=True)]
        if n == 2:
            items.append(dict(platform_item_id='ITEM-2-2', title='Mock linen pouch', sku='SKU-COMMON', quantity=1, unit_price='10.00', unit_weight='0.100', country_of_origin='US', source='mock', is_mock=True))
        subtotal = sum((Decimal(i['unit_price']) * i['quantity'] for i in items), Decimal('0'))
        total = subtotal + Decimal('7.00')
        shipments = []
        for p in range(1, 3 if n == 3 else 2):
            allocations = [{'item': i['platform_item_id'], 'quantity': 1 if n == 3 else i['quantity'], 'is_mock': True} for i in items]
            shipments.append(dict(package_reference=f'MOCK-PKG-{n:03}-{p}', carrier='MockCarrier', tracking_number=None if n == 4 else '00001234567890123456789012345678901234567890' if n == 1 else 'SHARED-TRACKING' if n in (2,3) else f'MOCKTRACK-{n:03}-{p}', shipping_date=None if n == 4 else day.date().isoformat(), weight=None if n == 9 else '0.500', length='20.000', width='15.000', height='5.000', measurement_unit='kg/cm', additional_insurance='N', insurance_value='0.00', shipment_purpose='Commercial', shipping_notes='固定模拟数据', email_label_to=f'labels{n}@example.com', address_translation_1=None, address_translation_2=None, notes_on_invoice=None, danger_goods='', allocations=allocations, source='mock', is_mock=True))
        transactions = [dict(source_transaction_id=f'PAY-{n:03}', type='payment', amount=format(total, '.2f'), currency='USD', occurred_at=stamp, description='Mock buyer payment', source='mock', is_mock=True), dict(source_transaction_id=f'FEE-{n:03}', type='fee', amount='-2.00', currency='USD', occurred_at=stamp, description='Mock order fee', source='mock', is_mock=True)]
        if n in (5,6):
            transactions.append(dict(source_transaction_id=f'REFUND-{n:03}', type='refund', amount='-5.00' if n == 5 else format(-total, '.2f'), currency='USD', occurred_at=stamp, description='Mock partial refund' if n == 5 else 'Mock full refund', source='mock', is_mock=True))
        data['orders'].append(dict(shop=shop, platform_order_id=number, status='unshipped' if n == 4 else 'refunded' if n == 6 else 'shipped', currency='USD', subtotal=format(subtotal, '.2f'), buyer_shipping_amount='5.00', tax_amount='2.00', discount_amount='0.00', total_amount=format(total, '.2f'), ordered_at=stamp, platform_updated_at=stamp, receiver_name=f'Fictional Buyer {n:02}', receiver_company=None, receiver_country='US', receiver_address1=None if n == 8 else f'{100+n} Imaginary Lane', receiver_address2=None, receiver_city='Fictional Town', receiver_state='MA', receiver_zip='01234', receiver_phone=None if n == 7 else '+1-202-555-0100', receiver_phone_ext=None, source='mock', is_mock=True, items=items, shipments=shipments, transactions=transactions))
    for n in (1,2):
        for kind, amount in [('fee', '-10.00'), ('payout', '-100.00')]:
            data['shop_transactions'].append(dict(shop=f'MOCK-SHOP-{n}', source_transaction_id=f'SHOP-{kind}-{n}', type=kind, amount=amount, currency='USD', occurred_at='2026-02-28T12:00:00+00:00', description=f'Mock shop {kind}; no order association', source='mock', is_mock=True))
    return data

if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'fixtures/mock.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
