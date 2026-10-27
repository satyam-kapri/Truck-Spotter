from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from rest_framework.test import APIClient
from backend import providers


def payload(**overrides):
    return {'origin':providers.DEMO_ORIGIN,'destination':providers.DEMO_DESTINATION,'departure':datetime.now(timezone.utc).isoformat(),'load_lb':28000,'spacing_miles':25,'mode':'demo',**overrides}


def test_full_demo_analysis_and_49_frames():
    client=APIClient()
    response=client.post('/api/route-analyses',payload(),format='json')
    assert response.status_code==200
    data=response.json()
    assert len(data['routes'])==3
    assert data['recommended_id']
    assert 'synthetic' in data['warnings'][0]
    for route in data['routes']:
        assert sum(route['summary']['miles_by_risk'].values())==pytest.approx(route['distance_miles'])
    corridor=client.get(f"/api/route-analyses/{data['id']}/corridor")
    assert corridor.status_code==200
    grid=corridor.json()
    assert len(grid['frames'])==49
    assert 0<len(grid['coordinates'])<=120
    assert all(len(f)==len(grid['coordinates']) for f in grid['frames'])


@pytest.mark.parametrize('override',[{'spacing_miles':15},{'load_lb':-1},{'departure':'2026-10-27T12:00:00'},{'origin':{'label':'bad','coordinates':[500,0]}}])
def test_validation(override):
    assert APIClient().post('/api/route-analyses',payload(**override),format='json').status_code==400


def test_expired_analysis():
    assert APIClient().get('/api/route-analyses/missing/corridor').status_code==410


def test_live_failure_does_not_fabricate_demo():
    with patch('backend.providers.routes',side_effect=providers.ProviderError('Provider unavailable')):
        r=APIClient().post('/api/route-analyses',payload(mode='live'),format='json')
    assert r.status_code==502
    assert 'routes' not in r.json()


def test_live_unknown_forecast_has_no_recommendation():
    with patch('backend.providers.routes',return_value=providers.demo_routes()[:1]),patch('backend.providers.fetch_forecasts',return_value=[{}]*100):
        response=APIClient().post('/api/route-analyses',payload(mode='live'),format='json')
    assert response.status_code==200
    data=response.json()
    assert data['recommended_id'] is None
    assert not data['routes'][0]['summary']['complete']
    assert any('three' in w for w in data['warnings'])
