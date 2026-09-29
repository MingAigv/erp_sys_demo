from datetime import datetime
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.models import Shop, Order, FinancialTransaction, SyncRun
from app.providers import MockDataProvider
from app.schemas import BatchLookup, ExportRequest, Page, Preview, LookupResult
from app.services.queries import serialize, order_query, paginate, get_order, detail, date_bounds
from app.services.sync import sync_mock
from app.services.export import prepare, export_workbook
from app.services.errors import BusinessError

router = APIRouter(prefix='/api/v1')

def db(request: Request):
    with request.app.state.sessions() as session:
        yield session

DB = Annotated[Session, Depends(db)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
ShopId = Annotated[int | None, Query(gt=0)]

@router.get('/health')
def health(session: DB):
    session.execute(text('SELECT 1'))
    try:
        session.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    except Exception as exc:
        raise BusinessError('DATABASE_NOT_INITIALIZED', '请先运行 alembic upgrade head', status=503) from exc
    return {'status': 'ok', 'database': 'ok'}

@router.get('/shops')
def shops(session: DB):
    return [serialize(s) for s in session.scalars(select(Shop).order_by(Shop.id))]

@router.post('/sync/mock')
def sync(session: DB):
    return serialize(sync_mock(session, MockDataProvider()))

@router.get('/sync-runs', response_model=Page)
def sync_runs(session: DB, page: PageNumber = 1, page_size: PageSize = 20):
    return paginate(session, select(SyncRun), page, page_size, SyncRun.id.desc())

@router.get('/orders', response_model=Page)
def orders(session: DB, shop_id: ShopId = None, order_number: str | None = None, tracking_number: str | None = None, sku: str | None = None, status: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, page: PageNumber = 1, page_size: PageSize = 20):
    stmt = order_query(shop_id, order_number, tracking_number, sku, status, date_from, date_to)
    return paginate(session, stmt, page, page_size, Order.ordered_at.desc(), Order.id.desc())

@router.post('/orders/batch-lookup', response_model=list[LookupResult])
def batch_lookup(body: BatchLookup, session: DB):
    result = []
    for value in body.values:
        matches = session.scalars(order_query(shop_id=body.shop_id, **{body.lookup_type: value}).order_by(Order.id)).all()
        result.append({'input_value': value, 'status': 'not_found' if not matches else 'matched' if len(matches) == 1 else 'ambiguous', 'orders': [serialize(o) for o in matches]})
    return result

@router.get('/orders/{order_id}')
def order_detail(order_id: int, session: DB):
    return detail(get_order(session, order_id))

@router.get('/financial-transactions', response_model=Page)
def financial_transactions(session: DB, shop_id: ShopId = None, order_id: Annotated[int | None, Query(gt=0)] = None, type: Literal['payment', 'refund', 'fee', 'adjustment', 'payout'] | None = None, currency: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, page: PageNumber = 1, page_size: PageSize = 20):
    date_bounds(date_from, date_to)
    stmt = select(FinancialTransaction)
    for column, value in [(FinancialTransaction.shop_id, shop_id), (FinancialTransaction.order_id, order_id), (FinancialTransaction.type, type), (FinancialTransaction.currency, currency)]:
        if value is not None:
            stmt = stmt.where(column == value)
    if date_from:
        stmt = stmt.where(FinancialTransaction.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(FinancialTransaction.occurred_at < date_to)
    return paginate(session, stmt, page, page_size, FinancialTransaction.occurred_at.desc(), FinancialTransaction.id.desc())

@router.post('/exports/postpony/preview', response_model=Preview)
def preview(body: ExportRequest, request: Request, session: DB):
    report, _, _ = prepare(session, body.order_ids, request.app.state.settings)
    if report['errors']:
        from fastapi.encoders import jsonable_encoder
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=422, content=jsonable_encoder({'code': 'EXPORT_VALIDATION_FAILED', 'message': '部分订单不满足导出要求', 'details': report['errors'], **report}))
    return report

@router.post('/exports/postpony')
def export(body: ExportRequest, request: Request, session: DB):
    payload = export_workbook(session, body.order_ids, request.app.state.settings)
    return Response(payload, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment; filename="postpony-orders.xlsx"'})
