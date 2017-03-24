from flask import json, url_for

import views
from models import APIKey


def test_sanity_check(client):
    response = client.get(url_for('api.sanity_check'))
    assert response.status_code == 200 and response.data.decode('utf-8') == ''
    
    
def test_api_view(request_context):
    status_code = 200
    body = 'bar'

    @views.api_view
    def v():
        return status_code, body

    result = v()
    assert result.status_code == status_code
    assert json.loads(result.data.decode('utf-8')) == body


def test_require_perms(app, db):
    jury_key = APIKey(perm_jury=True)
    master_key = APIKey(perm_master=True)
    db.session.add(jury_key)
    db.session.add(master_key)
    db.session.commit()

    @views.require_perms('master')
    def v():
        return 'foo'

    with app.test_request_context(headers=dict(api_key=jury_key.key)):
        result = v()
        assert result == (403, None)

    with app.test_request_context(headers=dict(api_key=master_key.key)):
        result = v()
        assert result == 'foo'

    with app.test_request_context(headers=dict()):
        result = v()
        assert result == (403, None)


def test_require_multiple_perms(app, db):
    jury_key = APIKey(perm_jury=True)
    master_key = APIKey(perm_master=True)
    db.session.add(jury_key)
    db.session.add(master_key)
    db.session.commit()

    @views.require_perms(('master', 'jury'))
    def v():
        return 200, 'foo'

    with app.test_request_context(headers=dict(api_key=jury_key.key)):
        result = v()
        assert result == (200, 'foo')

    with app.test_request_context(headers=dict(api_key=master_key.key)):
        result = v()
        assert result == (200, 'foo')

    with app.test_request_context(headers=dict()):
        result = v()
        assert result == (403, None)
