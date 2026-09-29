from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.config import Settings
from app.db import make_engine, session_factory
from app.api.routes import router
from app.services.errors import BusinessError

def create_app(settings=None):
    settings = settings or Settings()
    engine = make_engine(settings.database_path)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title='Etsy 本地订单管理（固定模拟数据）', version='1.0.0', lifespan=lifespan)
    app.state.settings, app.state.engine, app.state.sessions = settings, engine, session_factory(engine)
    app.include_router(router)

    @app.exception_handler(BusinessError)
    async def business_error(request, exc):
        return JSONResponse(status_code=exc.status, content={'code': exc.code, 'message': exc.message, 'details': exc.details})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        details = [{'field': '.'.join(map(str, e['loc'])), 'reason': e['msg']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'code': 'INVALID_PARAMETERS', 'message': '请求参数无效', 'details': details})

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={'code': 'HTTP_ERROR', 'message': str(exc.detail), 'details': []})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={'code': 'DATABASE_ERROR', 'message': '数据库不可用、未迁移或写入违反数据约束', 'details': []})

    return app
