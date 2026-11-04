"""Smoke test isolado, executado manualmente com PostgreSQL/Redis reais, nunca em produção."""
import hashlib
import json
import os
import secrets
import time
import httpx
from redis import Redis

url=os.environ['SMOKE_BASE_URL']
redis=Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
owner='smoke-'+secrets.token_hex(16)
sid=secrets.token_hex(32)
csrf=secrets.token_hex(32)
key='session:'+hashlib.sha256(sid.encode()).hexdigest()
redis.setex(key,60,json.dumps({'user':owner,'csrf':csrf,'created':time.time()}))
with httpx.Client(base_url=url,trust_env=False,headers={'Origin':os.environ['BASE_URL'],'X-CSRF-Token':csrf},cookies={'walleturbo_session':sid}) as client:
    try:
        assert client.get('/health/ready').status_code==200
        csv='data;descricao;valor;tipo\n2026-11-03;Mercado;12,34;despesa\n'
        response=client.post('/api/import/confirm',json={'content':csv})
        assert response.status_code==200,response.text
        assert response.json()=={'created':1,'duplicates':0}
        assert client.post('/api/import/confirm',json={'content':csv}).json()=={'created':0,'duplicates':1}
        assert client.get('/api/dashboard?month=2026-11').json()['expense_cents']==1234
        row=client.get('/api/privacy/export').json()['transactions'][0]
        assert client.delete('/api/transactions/'+row['id']).status_code==204
        assert client.get('/api/privacy/export').json()['transactions']==[]
        print('PASS: PostgreSQL/Redis reais: readiness, sessão, importação, deduplicação, saldo, exportação e exclusão.')
    finally:
        client.delete('/api/privacy/data',headers={'X-Confirm-Delete':'EXCLUIR'})
        redis.delete(key)
