import time
from unittest.mock import patch
import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from backend.corridor_tokens import compact_geometry
from backend.tests.test_api import payload


def new_analysis():
    response = APIClient().post('/api/route-analyses', payload(), format='json')
    assert response.status_code == 200
    return response.json()


def test_corridor_survives_loss_of_all_instance_cache():
    analysis = new_analysis()
    cache.clear()  # Simulate the next request landing on a fresh Vercel instance.
    response = APIClient().post(f"/api/route-analyses/{analysis['id']}/corridor", {'corridor_token': analysis['corridor_token']}, format='json')
    assert response.status_code == 200
    result = response.json()
    assert len(result['frames']) == 49
    assert 0 < len(result['coordinates']) <= 120
    assert all(len(frame) == len(result['coordinates']) for frame in result['frames'])


def test_no_cache_backend_is_needed_for_complete_trip_flow():
    with override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}):
        analysis = new_analysis()
        response = APIClient().post(f"/api/route-analyses/{analysis['id']}/corridor", {'corridor_token': analysis['corridor_token']}, format='json')
    assert response.status_code == 200


def test_changed_token_cannot_supply_modified_trip_context():
    analysis = new_analysis()
    token = analysis['corridor_token']
    corrupt = ('x' if token[0] != 'x' else 'y') + token[1:]
    response = APIClient().post(f"/api/route-analyses/{analysis['id']}/corridor", {'corridor_token': corrupt}, format='json')
    assert response.status_code == 400


def test_token_cannot_be_used_for_another_analysis():
    analysis = new_analysis()
    response = APIClient().post('/api/route-analyses/another-trip/corridor', {'corridor_token': analysis['corridor_token']}, format='json')
    assert response.status_code == 400


def test_expired_token_requires_a_new_analysis():
    analysis = new_analysis()
    future = time.time() + 901
    with patch('django.core.signing.time.time', return_value=future):
        response = APIClient().post(f"/api/route-analyses/{analysis['id']}/corridor", {'corridor_token': analysis['corridor_token']}, format='json')
    assert response.status_code == 410


@pytest.mark.parametrize('body', [{}, {'corridor_token': 42}, {'corridor_token': 'x'*500001}, []])
def test_missing_or_malformed_token_rejected(body):
    response = APIClient().post('/api/route-analyses/trip/corridor', body, format='json')
    assert response.status_code == 400


def test_geometry_compaction_is_only_for_corridor_and_preserves_endpoints():
    coordinates = [[-87, 41], [-86.999, 41], [-86.998, 41], [-86.5, 40]]
    original = [p[:] for p in coordinates]
    compact = compact_geometry(coordinates)
    assert compact == [coordinates[0], coordinates[-1]]
    assert coordinates == original
