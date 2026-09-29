from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import create_engine, event, Integer, String
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class Money(TypeDecorator):
    """USD minor units; never convert money through a float."""
    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, float):
            raise ValueError('Money must not be float')
        amount = Decimal(value)
        if not amount.is_finite() or amount != amount.quantize(Decimal('.01')):
            raise ValueError('Money must have at most two decimal places')
        return int(amount * 100)

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value) / Decimal(100)


class Measure(TypeDecorator):
    """Fixed 0.001 precision, stored as canonical decimal text (not money)."""
    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, float):
            raise ValueError('Measure must not be float')
        value = Decimal(value)
        if not value.is_finite() or value != value.quantize(Decimal('.001')):
            raise ValueError('Measure precision must be <= 0.001')
        return format(value, '.3f')

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


class UTCDateTime(TypeDecorator):
    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError('Timezone required')
        return value.astimezone(timezone.utc).isoformat(timespec='microseconds')

    def process_result_value(self, value, dialect):
        return datetime.fromisoformat(value) if value else None


def make_engine(path):
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine('sqlite:///' + path.as_posix(), connect_args={'check_same_thread': False, 'timeout': 15})

    @event.listens_for(engine, 'connect')
    def sqlite_settings(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=15000')

    return engine


def session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)
