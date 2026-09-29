from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_path: Path = Path('data/etsy.sqlite3')
    postpony_template: Path = Path('templates/postpony.xlsx')
    export_order_id_max_length: int = Field(default=30, ge=1, le=32767)
    export_address_max_length: int = Field(default=35, ge=1, le=32767)
