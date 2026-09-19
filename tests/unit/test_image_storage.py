import os, sys, types
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


@pytest.fixture
def set_env(monkeypatch):
    monkeypatch.setenv('TOOL_TOKEN', 'x')
    monkeypatch.setenv('MINIO_ENDPOINT', 'http://minio:9000')
    monkeypatch.setenv('MINIO_ACCESS_KEY', 'minioadmin')
    monkeypatch.setenv('MINIO_SECRET_KEY', 'secret')
    monkeypatch.setenv('MINIO_BUCKET', 'pentest-self-reports')
    monkeypatch.setenv('MINIO_REGION', 'us-east-1')


class _FakeClient:
    def put_object(self, **kw):
        self.saved = kw


class _FakeBoto:
    def client(self, *a, **k):
        return _FakeClient()


def test_minio_default_mode_and_object_key(set_env, monkeypatch):
    import core.image_hosting as ih
    monkeypatch.setitem(sys.modules, 'boto3', _FakeBoto())
    key = ih.upload_to_minio(b'\x89PNG\r\n\x1a\nabc')
    assert key and key.startswith('screenshots/') and key.endswith('.png')
