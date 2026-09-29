import argparse
from app.config import Settings
from app.db import make_engine, session_factory
from app.providers import MockDataProvider
from app.services.sync import sync_mock
from app.services.queries import serialize
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['sync-mock', 'inspect-template'])
    args = parser.parse_args()
    settings = Settings()
    if args.command == 'inspect-template':
        from app.services.export import load_template
        book = load_template(settings.postpony_template)
        report = {'sheets': book.sheetnames, 'headers': [], 'validations': []}
        for cell in book['Import Template'][1]:
            report['headers'].append({'column': cell.column_letter, 'value': cell.value, 'comment': cell.comment.text if cell.comment else None, 'font_color': str(cell.font.color)})
        for validation in book['Import Template'].data_validations.dataValidation:
            report['validations'].append({'range': str(validation.sqref), 'type': validation.type, 'formula1': validation.formula1})
        report['remarks'] = [[cell.value for cell in row] for row in book['Remarks']]
        report['data_table'] = [[cell.value for cell in row] for row in book['Data table']]
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return
    engine = make_engine(settings.database_path)
    try:
        with session_factory(engine)() as session:
            print(json.dumps(serialize(sync_mock(session, MockDataProvider())), ensure_ascii=False, default=str))
    finally:
        engine.dispose()

if __name__ == '__main__':
    main()
