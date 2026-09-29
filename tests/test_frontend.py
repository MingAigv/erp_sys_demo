def test_frontend_home_and_assets_are_served(environment):
    _, client, _, _ = environment
    response = client.get('/')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    assert '订单工作台' in response.text
    assert 'id="export-all"' in response.text
    assert response.headers['cache-control'] == 'no-cache'
    for filename in ('style.css', 'app.mjs', 'utils.mjs', 'favicon.svg'):
        asset = client.get('/static/' + filename)
        assert asset.status_code == 200
        assert len(asset.content) > 20
    assert client.get('/favicon.ico').status_code == 200


def test_frontend_does_not_replace_api_or_docs(environment):
    _, client, _, _ = environment
    assert client.get('/api/v1/health').json()['status'] == 'ok'
    assert client.get('/docs').status_code == 200
    assert client.get('/api/v1/nonexistent').status_code == 404
    assert client.get('/static/nonexistent.js').status_code == 404


def test_assets_resolve_independent_of_working_directory(environment, monkeypatch):
    from app.main import create_app
    from fastapi.testclient import TestClient
    app, _, _, tmp_path = environment
    monkeypatch.chdir(tmp_path)
    with TestClient(create_app(app.state.settings)) as client:
        assert client.get('/').status_code == 200
        assert client.get('/static/app.mjs').status_code == 200


def test_frontend_loads_without_database_initialization(tmp_path):
    from app.main import create_app
    from app.config import Settings
    from fastapi.testclient import TestClient
    with TestClient(create_app(Settings(database_path=tmp_path / 'new.sqlite3'))) as client:
        assert client.get('/').status_code == 200
        assert client.get('/static/app.mjs').status_code == 200
        assert client.get('/api/v1/health').status_code == 503
