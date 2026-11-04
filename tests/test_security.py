import json
import time
import pytest
from app.security import COOKIE, session_key
from tests.test_finance import ENTRY


def test_auth_required_and_no_dev_bypass(client):
    assert client.get('/api/dashboard?month=2026-11').status_code==401
    assert client.get('/api/me',headers={'Authorization':'Bearer fake','X-User-Id':'alice'}).status_code==401
    assert client.get('/auth/login').status_code==503


def test_isolation_across_users(client, login):
    login('alice')
    row=client.post('/api/transactions',json=ENTRY).json()
    goal={'name':'Reserva','target_cents':50000,'saved_cents':1000,'deadline':'2027-01-01'}
    goal_id=client.post('/api/goals',json=goal).json()['id']
    login('bob')
    assert client.get('/api/dashboard?month=2026-11').json()['transactions']==[]
    assert client.put('/api/transactions/'+row['id'],json=ENTRY).status_code==404
    assert client.delete('/api/transactions/'+row['id']).status_code==404
    assert client.put('/api/goals/'+goal_id,json=goal).status_code==404
    assert client.get('/api/privacy/export').json()=={'transactions':[],'goals':[]}
    login('alice')
    assert len(client.get('/api/privacy/export').json()['transactions'])==1


@pytest.mark.parametrize('headers', [{'Origin':'https://evil.example','X-CSRF-Token':'test-csrf'},{'Origin':'http://testserver','X-CSRF-Token':'wrong'}])
def test_csrf(client, login, headers):
    login()
    assert client.post('/api/transactions',json=ENTRY,headers=headers).status_code==403


def test_headers_host_and_body_limit(client):
    result=client.get('/')
    assert "frame-ancestors 'none'" in result.headers['Content-Security-Policy']
    assert result.headers['X-Content-Type-Options']=='nosniff'
    assert client.get('/',headers={'Host':'evil.example'}).status_code==400
    assert client.post('/api/transactions',content=b'x'*300001).status_code==413


def test_rate_limit(client):
    for _ in range(120):
        assert client.get('/api/me').status_code==401
    assert client.get('/api/me').status_code==429


def test_redis_failure_closed(client, monkeypatch):
    from redis.exceptions import ConnectionError
    def fail(*a,**k):
        raise ConnectionError()
    monkeypatch.setattr(client.redis,'eval',fail)
    assert client.get('/api/me').status_code==503


def test_cookie_expiry_and_logout(client, login):
    login()
    response=client.get('/api/me')
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=lax' in response.headers['set-cookie']
    assert client.post('/api/logout').status_code==200
    assert client.get('/api/me').status_code==401


def test_absolute_session_expiry(client, login):
    login()
    key=session_key('a'*64)
    client.redis.set(key,json.dumps({'user':'alice','csrf':'test-csrf','created':time.time()-28801}))
    assert client.get('/api/me').status_code==401


def test_privacy_delete_requires_confirmation_and_preserves_other_owner(client, login):
    login('bob')
    client.post('/api/transactions',json=ENTRY)
    login('alice')
    client.post('/api/transactions',json=ENTRY)
    assert client.delete('/api/privacy/data').status_code==400
    assert client.delete('/api/privacy/data',headers={'X-Confirm-Delete':'EXCLUIR'}).status_code==200
    login('alice')
    assert client.get('/api/privacy/export').json()['transactions']==[]
    login('bob')
    assert len(client.get('/api/privacy/export').json()['transactions'])==1


@pytest.mark.parametrize('claims,status', [
    ({'sub':'123','iss':'https://identity.example','acr':'1'},403),
    ({'sub':'123','iss':'https://evil.example','acr':'2'},403),
    ({'sub':'123','iss':'https://identity.example','acr':'2'},303),
])
def test_callback_mfa_issuer_and_rotation(client, login, monkeypatch, claims, status):
    from types import SimpleNamespace
    from app import main
    login()
    old_key=session_key('a'*64)
    async def token(request):
        return {'userinfo':claims}
    monkeypatch.setattr(main.conf,'oidc_issuer','https://identity.example')
    monkeypatch.setattr(main,'oauth',SimpleNamespace(identity=SimpleNamespace(authorize_access_token=token)))
    response=client.get('/auth/callback',follow_redirects=False)
    assert response.status_code==status
    if status==303:
        assert not client.redis.exists(old_key)
        assert client.get('/api/me').status_code==200


def test_production_configuration_fails_closed():
    from app.config import Settings
    with pytest.raises(RuntimeError):
        Settings(app_env='production',base_url='http://local',oidc_issuer='').validate_auth()
