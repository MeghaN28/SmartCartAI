import os
import sys
from unittest.mock import patch

# make imports relative-workspace-friendly
HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agent


def test_notify_decision_success(monkeypatch):
    called = {}

    def fake_post(url, json, timeout):
        called['url'] = url
        called['json'] = json

        class R:
            status_code = 200

            def json(self):
                return {'decision': 'ok'}

            text = 'ok'

        return R()

    monkeypatch.setattr('requests.post', fake_post)
    res = agent.notify_decision({'inventory_id': '123'})
    assert res == {'decision': 'ok'}
    assert called['url'] == agent.DECISION_AGENT_URL


def test_notify_decision_exception(monkeypatch):
    def fake_post(url, json, timeout):
        raise Exception("boom")

    monkeypatch.setattr('requests.post', fake_post)
    res = agent.notify_decision({'inventory_id': 'x'})
    assert 'error' in res


def test_inventory_endpoint_calls_decision(monkeypatch):
    def fake_post(url, json, timeout):
        class R:
            status_code = 200

            def json(self):
                return {'ok': True}

            text = 'ok'

        return R()

    monkeypatch.setattr('requests.post', fake_post)
    client = agent.app.test_client()
    rv = client.post('/inventory', json={'inventory_id': 'X'})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['result'] == {'ok': True}
