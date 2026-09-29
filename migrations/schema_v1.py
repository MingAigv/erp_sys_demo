"""Frozen v1 SQLite schema; independent of evolving ORM metadata."""
TABLES = ['shops', 'orders', 'order_items', 'shipments', 'shipment_items', 'financial_transactions', 'sync_runs']
MOCK = "source TEXT NOT NULL DEFAULT 'mock', is_mock BOOLEAN NOT NULL DEFAULT 1"
DDL = [
    f'''CREATE TABLE shops (
        id INTEGER PRIMARY KEY, platform_shop_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL, {MOCK})''',
    f'''CREATE TABLE orders (
        id INTEGER PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shops(id),
        platform_order_id TEXT NOT NULL, status TEXT NOT NULL, currency TEXT NOT NULL,
        subtotal INTEGER NOT NULL, buyer_shipping_amount INTEGER NOT NULL,
        tax_amount INTEGER NOT NULL, discount_amount INTEGER NOT NULL, total_amount INTEGER NOT NULL,
        ordered_at TEXT NOT NULL, platform_updated_at TEXT NOT NULL,
        receiver_name TEXT, receiver_company TEXT, receiver_country TEXT,
        receiver_address1 TEXT, receiver_address2 TEXT, receiver_city TEXT, receiver_state TEXT,
        receiver_zip TEXT, receiver_phone TEXT, receiver_phone_ext TEXT, internal_notes TEXT,
        {MOCK}, UNIQUE(shop_id, platform_order_id))''',
    f'''CREATE TABLE order_items (
        id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
        platform_item_id TEXT NOT NULL, title TEXT NOT NULL, sku TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0 AND typeof(quantity) = 'integer'),
        unit_price INTEGER NOT NULL CHECK(unit_price >= 0), unit_weight TEXT, country_of_origin TEXT,
        {MOCK}, UNIQUE(order_id, platform_item_id))''',
    f'''CREATE TABLE shipments (
        id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
        package_reference TEXT NOT NULL UNIQUE, carrier TEXT, tracking_number TEXT,
        shipping_date DATE, weight TEXT, length TEXT, width TEXT, height TEXT,
        measurement_unit TEXT, additional_insurance TEXT, insurance_value INTEGER,
        shipment_purpose TEXT, shipping_notes TEXT, email_label_to TEXT,
        address_translation_1 TEXT, address_translation_2 TEXT, notes_on_invoice TEXT,
        danger_goods TEXT, {MOCK})''',
    f'''CREATE TABLE shipment_items (
        shipment_id INTEGER NOT NULL REFERENCES shipments(id),
        order_item_id INTEGER NOT NULL REFERENCES order_items(id),
        quantity INTEGER NOT NULL CHECK(quantity > 0 AND typeof(quantity) = 'integer'),
        {MOCK}, PRIMARY KEY(shipment_id, order_item_id))''',
    f'''CREATE TABLE financial_transactions (
        id INTEGER PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shops(id),
        order_id INTEGER REFERENCES orders(id), source_transaction_id TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('payment','refund','fee','adjustment','payout')),
        amount INTEGER NOT NULL, currency TEXT NOT NULL, occurred_at TEXT NOT NULL,
        description TEXT NOT NULL, {MOCK}, UNIQUE(shop_id, source_transaction_id),
        CHECK((type != 'payment' OR amount >= 0) AND (type NOT IN ('refund','fee','payout') OR amount <= 0)))''',
    f'''CREATE TABLE sync_runs (
        id INTEGER PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL,
        finished_at TEXT, added INTEGER NOT NULL DEFAULT 0, updated INTEGER NOT NULL DEFAULT 0,
        unchanged INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
        error_summary TEXT, {MOCK})''',
]
for table, columns in {
    'orders': ['shop_id', 'platform_order_id', 'ordered_at'],
    'order_items': ['order_id', 'sku'],
    'shipments': ['order_id', 'tracking_number'],
    'financial_transactions': ['shop_id', 'order_id', 'type', 'occurred_at'],
}.items():
    for column in columns:
        DDL.append(f'CREATE INDEX ix_{table}_{column} ON {table} ({column})')

for operation in ('INSERT', 'UPDATE'):
    exclude = '' if operation == 'INSERT' else 'AND NOT (shipment_id = OLD.shipment_id AND order_item_id = OLD.order_item_id)'
    DDL.append(f'''CREATE TRIGGER allocation_{operation.lower()} BEFORE {operation} ON shipment_items
    BEGIN
        SELECT CASE WHEN
          (SELECT order_id FROM shipments WHERE id = NEW.shipment_id) !=
          (SELECT order_id FROM order_items WHERE id = NEW.order_item_id)
          THEN RAISE(ABORT, 'CROSS_ORDER_ALLOCATION') END;
        SELECT CASE WHEN NEW.quantity + COALESCE((SELECT SUM(quantity) FROM shipment_items
          WHERE order_item_id = NEW.order_item_id {exclude}), 0) >
          (SELECT quantity FROM order_items WHERE id = NEW.order_item_id)
          THEN RAISE(ABORT, 'OVER_ALLOCATION') END;
    END''')
    DDL.append(f'''CREATE TRIGGER finance_{operation.lower()} BEFORE {operation} ON financial_transactions
    WHEN NEW.order_id IS NOT NULL BEGIN
        SELECT CASE WHEN NEW.shop_id != (SELECT shop_id FROM orders WHERE id = NEW.order_id)
          THEN RAISE(ABORT, 'CROSS_SHOP_TRANSACTION') END;
    END''')

DDL.extend([
    '''CREATE TRIGGER item_quantity_update BEFORE UPDATE OF quantity ON order_items
    WHEN NEW.quantity < (SELECT COALESCE(SUM(quantity),0) FROM shipment_items WHERE order_item_id=OLD.id)
    BEGIN SELECT RAISE(ABORT, 'PURCHASE_BELOW_ALLOCATION'); END''',
    '''CREATE TRIGGER item_order_update BEFORE UPDATE OF order_id ON order_items
    WHEN NEW.order_id != OLD.order_id AND EXISTS(SELECT 1 FROM shipment_items WHERE order_item_id=OLD.id)
    BEGIN SELECT RAISE(ABORT, 'ALLOCATED_ITEM_ORDER_IMMUTABLE'); END''',
    '''CREATE TRIGGER shipment_order_update BEFORE UPDATE OF order_id ON shipments
    WHEN NEW.order_id != OLD.order_id AND EXISTS(SELECT 1 FROM shipment_items WHERE shipment_id=OLD.id)
    BEGIN SELECT RAISE(ABORT, 'ALLOCATED_SHIPMENT_ORDER_IMMUTABLE'); END''',
    '''CREATE TRIGGER order_shop_update BEFORE UPDATE OF shop_id ON orders
    WHEN NEW.shop_id != OLD.shop_id AND EXISTS(SELECT 1 FROM financial_transactions WHERE order_id=OLD.id)
    BEGIN SELECT RAISE(ABORT, 'TRANSACTION_ORDER_SHOP_IMMUTABLE'); END''',
])
