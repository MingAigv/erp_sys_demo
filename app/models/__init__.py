from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base, Money, Measure, UTCDateTime


class MockRecord:
    source: Mapped[str] = mapped_column(String, default='mock')
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)


class Shop(MockRecord, Base):
    __tablename__ = 'shops'
    id: Mapped[int] = mapped_column(primary_key=True)
    platform_shop_id: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str]


class Order(MockRecord, Base):
    __tablename__ = 'orders'
    __table_args__ = (UniqueConstraint('shop_id', 'platform_order_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey('shops.id'), index=True)
    platform_order_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str]
    currency: Mapped[str]
    subtotal: Mapped[Decimal] = mapped_column(Money)
    buyer_shipping_amount: Mapped[Decimal] = mapped_column(Money)
    tax_amount: Mapped[Decimal] = mapped_column(Money)
    discount_amount: Mapped[Decimal] = mapped_column(Money)
    total_amount: Mapped[Decimal] = mapped_column(Money)
    ordered_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    platform_updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    receiver_name: Mapped[str | None]
    receiver_company: Mapped[str | None]
    receiver_country: Mapped[str | None]
    receiver_address1: Mapped[str | None]
    receiver_address2: Mapped[str | None]
    receiver_city: Mapped[str | None]
    receiver_state: Mapped[str | None]
    receiver_zip: Mapped[str | None]
    receiver_phone: Mapped[str | None]
    receiver_phone_ext: Mapped[str | None]
    internal_notes: Mapped[str | None]
    items: Mapped[list['OrderItem']] = relationship(cascade='all, delete-orphan')
    shipments: Mapped[list['Shipment']] = relationship(cascade='all, delete-orphan')
    transactions: Mapped[list['FinancialTransaction']] = relationship()


class OrderItem(MockRecord, Base):
    __tablename__ = 'order_items'
    __table_args__ = (UniqueConstraint('order_id', 'platform_item_id'), CheckConstraint('quantity > 0'), CheckConstraint('unit_price >= 0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), index=True)
    platform_item_id: Mapped[str]
    title: Mapped[str]
    sku: Mapped[str] = mapped_column(String, index=True)
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Money)
    unit_weight: Mapped[Decimal | None] = mapped_column(Measure)
    country_of_origin: Mapped[str | None]


class Shipment(MockRecord, Base):
    __tablename__ = 'shipments'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), index=True)
    package_reference: Mapped[str] = mapped_column(String, unique=True)
    carrier: Mapped[str | None]
    tracking_number: Mapped[str | None] = mapped_column(String, index=True)
    shipping_date: Mapped[date | None] = mapped_column(Date)
    weight: Mapped[Decimal | None] = mapped_column(Measure)
    length: Mapped[Decimal | None] = mapped_column(Measure)
    width: Mapped[Decimal | None] = mapped_column(Measure)
    height: Mapped[Decimal | None] = mapped_column(Measure)
    measurement_unit: Mapped[str | None]
    additional_insurance: Mapped[str | None]
    insurance_value: Mapped[Decimal | None] = mapped_column(Money)
    shipment_purpose: Mapped[str | None]
    shipping_notes: Mapped[str | None]
    email_label_to: Mapped[str | None]
    address_translation_1: Mapped[str | None]
    address_translation_2: Mapped[str | None]
    notes_on_invoice: Mapped[str | None]
    danger_goods: Mapped[str | None]
    allocations: Mapped[list['ShipmentItem']] = relationship(cascade='all, delete-orphan')


class ShipmentItem(MockRecord, Base):
    __tablename__ = 'shipment_items'
    __table_args__ = (CheckConstraint('quantity > 0'),)
    shipment_id: Mapped[int] = mapped_column(ForeignKey('shipments.id'), primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey('order_items.id'), primary_key=True)
    quantity: Mapped[int]


class FinancialTransaction(MockRecord, Base):
    __tablename__ = 'financial_transactions'
    __table_args__ = (UniqueConstraint('shop_id', 'source_transaction_id'), CheckConstraint("type IN ('payment','refund','fee','adjustment','payout')"), CheckConstraint("(type != 'payment' OR amount >= 0) AND (type NOT IN ('refund','fee','payout') OR amount <= 0)"))
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey('shops.id'), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey('orders.id'), index=True)
    source_transaction_id: Mapped[str]
    type: Mapped[str] = mapped_column(String, index=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str]
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    description: Mapped[str]


class SyncRun(MockRecord, Base):
    __tablename__ = 'sync_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str]
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    added: Mapped[int] = mapped_column(default=0)
    updated: Mapped[int] = mapped_column(default=0)
    unchanged: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[str | None]
