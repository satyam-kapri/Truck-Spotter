from datetime import datetime, timezone
from unittest.mock import patch
from backend.providers import routes, ProviderError


def raw(coords):
    return {'geometry':{'coordinates':coords},'legs':[{'annotation':{'distance':[100000]*(len(coords)-1),'duration':[3600]*(len(coords)-1)}}]}


def test_third_route_is_provider_computed_and_labeled():
    initial={'code':'Ok','routes':[raw([[-87,41],[-86.5,39],[-86,36]]),raw([[-87,41],[-87.5,39],[-86,36]])]}
    detour={'code':'Ok','routes':[raw([[-87,41],[-88,39],[-86,36]])]}
    with patch.dict('os.environ',{'MAPBOX_TOKEN':''}),patch('backend.providers.get_json',side_effect=[initial,detour]) as get:
        result=routes([-87,41],[-86,36],datetime.now(timezone.utc))
    assert len(result)==3
    assert 'via_coordinates' in result[-1]
    assert 'via point' in result[-1]['name']
    assert get.call_count==2


def test_failed_detours_keep_actual_count():
    initial={'code':'Ok','routes':[raw([[-87,41],[-86.5,39],[-86,36]])]}
    with patch.dict('os.environ',{'MAPBOX_TOKEN':''}),patch('backend.providers.get_json',side_effect=[initial,ProviderError('down'),ProviderError('down')]):
        result=routes([-87,41],[-86,36],datetime.now(timezone.utc))
    assert len(result)==1
