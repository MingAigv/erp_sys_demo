from typing import Literal, Annotated, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

class RequestModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ExportRequest(RequestModel):
    order_ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(min_length=1, max_length=500)

class BatchLookup(RequestModel):
    lookup_type: Literal['order_number', 'tracking_number']
    values: list[Annotated[str, Field(strict=True, max_length=256)]] = Field(min_length=1, max_length=500)
    shop_id: Annotated[int, Field(strict=True, gt=0)] | None = None

    @field_validator('values')
    @classmethod
    def strip_values(cls, values):
        values = [v.strip() for v in values]
        if any(not v for v in values):
            raise ValueError('查询值不能为空')
        return values

class Page(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[dict[str, Any]]

class Issue(BaseModel):
    order_id: int | None = None
    field: str
    reason: str
    code: str

class Preview(BaseModel):
    valid: bool
    estimated_rows: int
    selected_orders: int
    errors: list[Issue]
    warnings: list[Issue]

class LookupResult(BaseModel):
    input_value: str
    status: Literal['matched', 'not_found', 'ambiguous']
    orders: list[dict[str, Any]]
