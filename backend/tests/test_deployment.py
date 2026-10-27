import json
import os
import subprocess
import sys
from unittest.mock import patch

from rest_framework.test import APIClient


def load_vercel_settings(**overrides):
    env = {**os.environ, 'VERCEL': '1', 'DJANGO_SECRET_KEY': 'deployment-test-secret', 'REDIS_URL': 'redis://cache.invalid:6379/0', 'VERCEL_URL': 'test-preview.vercel.app', 'VERCEL_PROJECT_PRODUCTION_URL': 'truckrouteplanner.vercel.app'}
    env.pop('DJANGO_DEBUG', None)
    env.update(overrides)
    return subprocess.run([sys.executable, '-c', "import json; from backend import settings as s; print(json.dumps({'debug': s.DEBUG, 'hosts': s.ALLOWED_HOSTS, 'cache': s.CACHES['default']['BACKEND']}))"], env=env, capture_output=True, text=True)


def test_vercel_uses_shared_cache_production_mode_and_deployment_hosts():
    result = load_vercel_settings()
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    assert config['debug'] is False
    assert config['cache'] == 'django.core.cache.backends.redis.RedisCache'
    assert 'test-preview.vercel.app' in config['hosts']
    assert 'truckrouteplanner.vercel.app' in config['hosts']


def test_vercel_rejects_a_missing_secret():
    result = load_vercel_settings(DJANGO_SECRET_KEY='')
    assert result.returncode != 0
    assert 'Set DJANGO_SECRET_KEY' in result.stderr


def test_vercel_requires_cross_instance_analysis_storage():
    result = load_vercel_settings(REDIS_URL='')
    assert result.returncode != 0
    assert 'Set REDIS_URL' in result.stderr


def test_rest_redis_url_is_not_accepted_as_a_tcp_connection():
    result = load_vercel_settings(REDIS_URL='https://cache.invalid')
    assert result.returncode != 0
    assert 'not a Redis REST API URL' in result.stderr


def test_health_does_not_require_the_cache_service():
    with patch('backend.views.cache.get', side_effect=AssertionError('Health must not touch cache')):
        response = APIClient().get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_missing_api_endpoints_return_json_for_get_and_post():
    client = APIClient()
    for request in (client.get, client.post):
        response = request('/api/missing-endpoint')
        assert response.status_code == 404
        assert response['Content-Type'].startswith('application/json')
        assert response.json()['error'] == 'API endpoint not found.'
