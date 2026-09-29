from typing import Protocol
import json
from pathlib import Path

class DataProvider(Protocol):
    def load(self) -> dict: ...

class MockDataProvider:
    def load(self) -> dict:
        return json.loads((Path(__file__).resolve().parents[2] / 'fixtures/mock.json').read_text(encoding='utf-8'))
