"""Dependency-light checks: python -m unittest discover -s tests -p test_portable.py -v.

Runs actual frozen SQL constraints and deterministic fixtures, without pytest/FastAPI.
"""
import hashlib
import json
from pathlib import Path
import runpy
import sqlite3
import unittest
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]

class PortableTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.schema = runpy.run_path(str(ROOT / 'migrations/schema_v1.py'))
        for statement in self.schema['DDL']:
            self.db.execute(statement)
        self.data = json.loads((ROOT / 'fixtures/mock.json').read_text(encoding='utf-8'))
        self.db.execute("INSERT INTO shops(id, platform_shop_id, name) VALUES(1,'S1','Mock1'),(2,'S2','Mock2')")
        for n in (1, 2):
            self.db.execute('''INSERT INTO orders(id,shop_id,platform_order_id,status,currency,subtotal,buyer_shipping_amount,tax_amount,discount_amount,total_amount,ordered_at,platform_updated_at)
            VALUES(?,?,?,'shipped','USD',2000,500,200,0,2700,'2026-01-01T00:00:00.000000+00:00','2026-01-01T00:00:00.000000+00:00')''', (n, n, '0001001'))
            self.db.execute('INSERT INTO order_items(id,order_id,platform_item_id,title,sku,quantity,unit_price) VALUES(?,?,?,\'Mock\',\'000SKU\',2,2000)', (n, n, f'I{n}'))
            self.db.execute('INSERT INTO shipments(id,order_id,package_reference) VALUES(?,?,?)', (n, n, f'P{n}'))
        self.db.execute("INSERT INTO shipments(id,order_id,package_reference) VALUES(3,1,'P3')")

    def tearDown(self):
        self.db.close()

    def test_fixed_fixture_deterministic(self):
        generated = runpy.run_path(str(ROOT / 'scripts/build_fixtures.py'))['build']()
        self.assertEqual(self.data, generated)
        self.assertEqual(len(self.data['shops']), 2)
        self.assertEqual(len(self.data['orders']), 50)
        self.assertEqual(sum(len(o['transactions']) for o in self.data['orders']) + len(self.data['shop_transactions']), 106)

    def test_fixture_money_and_mock_flags(self):
        for order in self.data['orders']:
            self.assertTrue(order['is_mock'])
            self.assertEqual(Decimal(order['subtotal']) + Decimal(order['buyer_shipping_amount']) + Decimal(order['tax_amount']) - Decimal(order['discount_amount']), Decimal(order['total_amount']))
            self.assertEqual(sum(Decimal(i['unit_price']) * i['quantity'] for i in order['items']), Decimal(order['subtotal']))
            for record in order['items'] + order['shipments'] + order['transactions']:
                self.assertTrue(record['is_mock'])
            for tx in order['transactions']:
                self.assertEqual(Decimal(tx['amount']) >= 0, tx['type'] == 'payment')
        self.assertTrue(all(t['is_mock'] and Decimal(t['amount']) < 0 for t in self.data['shop_transactions']))

    def test_fixture_allocations_exact(self):
        for order in self.data['orders']:
            for item in order['items']:
                self.assertEqual(sum(a['quantity'] for s in order['shipments'] for a in s['allocations'] if a['item'] == item['platform_item_id']), item['quantity'])

    def test_sql_cross_order_allocation(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'CROSS_ORDER_ALLOCATION'):
            self.db.execute('INSERT INTO shipment_items(shipment_id,order_item_id,quantity) VALUES(1,2,1)')

    def test_sql_overallocation_insert_and_update(self):
        self.db.execute('INSERT INTO shipment_items(shipment_id,order_item_id,quantity) VALUES(1,1,1),(3,1,1)')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'OVER_ALLOCATION'):
            self.db.execute('UPDATE shipment_items SET quantity=2 WHERE shipment_id=1')
        self.db.execute('DELETE FROM shipment_items WHERE shipment_id=3')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'OVER_ALLOCATION'):
            self.db.execute('INSERT INTO shipment_items(shipment_id,order_item_id,quantity) VALUES(3,1,2)')

    def test_sql_parent_quantity_and_ownership_guards(self):
        self.db.execute('INSERT INTO shipment_items(shipment_id,order_item_id,quantity) VALUES(1,1,2)')
        for statement in ('UPDATE order_items SET quantity=1 WHERE id=1', 'UPDATE order_items SET order_id=2 WHERE id=1', 'UPDATE shipments SET order_id=2 WHERE id=1'):
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(statement)

    def test_sql_financial_sign_and_shop_guards(self):
        statement = "INSERT INTO financial_transactions(shop_id,order_id,source_transaction_id,type,amount,currency,occurred_at,description) VALUES(?,?,?,?,?,'USD','2026-01-01','Mock')"
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(statement, (1, 1, 'bad-fee', 'fee', 200))
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'CROSS_SHOP_TRANSACTION'):
            self.db.execute(statement, (2, 1, 'bad-shop', 'payment', 200))
        self.db.execute(statement, (1, None, 'shop-fee', 'fee', -200))
        self.assertIsNone(self.db.execute("SELECT order_id FROM financial_transactions WHERE source_transaction_id='shop-fee'").fetchone()[0])

    def test_sql_string_precision_and_foreign_keys(self):
        tracking = '00001234567890123456789012345678901234567890'
        self.db.execute('UPDATE shipments SET tracking_number=? WHERE id=1', (tracking,))
        self.db.execute("UPDATE orders SET receiver_zip='01234',receiver_phone='+1-202-555-0100' WHERE id=1")
        self.assertEqual(self.db.execute('SELECT tracking_number FROM shipments WHERE id=1').fetchone()[0], tracking)
        self.assertEqual(self.db.execute('SELECT receiver_zip FROM orders WHERE id=1').fetchone()[0], '01234')
        self.assertEqual(self.db.execute('SELECT typeof(total_amount) FROM orders WHERE id=1').fetchone()[0], 'integer')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('INSERT INTO shipments(order_id,package_reference) VALUES(9999,\'BAD\')')

    def test_sql_unique_keys(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO shops(platform_shop_id,name) VALUES('S1','Duplicate')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO shipments(order_id,package_reference) VALUES(1,'P1')")

    def test_frozen_schema_reversible(self):
        for table in reversed(self.schema['TABLES']):
            self.db.execute(f'DROP TABLE {table}')
        for statement in self.schema['DDL']:
            self.db.execute(statement)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 0)

if __name__ == '__main__':
    unittest.main()
