from datetime import datetime, timezone
import pytest
from backend.domain import risk, checkpoints, summarize, recommend, MILE
from backend.providers import at_time


@pytest.mark.parametrize('value,level', [(24.99,'Low'),(25,'Moderate'),(34.99,'Moderate'),(35,'High'),(44.99,'High'),(45,'Severe'),(54.99,'Severe'),(55,'No Travel')])
def test_wind_boundaries(value, level):
    assert risk(value,0,0,0)['level'] == level


@pytest.mark.parametrize('value,level', [(.099,'Low'),(.10,'Moderate'),(.249,'Moderate'),(.25,'High'),(.499,'High'),(.5,'Severe'),(1,'Severe'),(1.001,'No Travel')])
def test_rain_boundaries(value, level):
    assert risk(0,value,0,0)['level'] == level


@pytest.mark.parametrize('value,level', [(.49,'Low'),(.5,'Moderate'),(.999,'Moderate'),(1,'High'),(1.999,'High'),(2,'Severe'),(3,'Severe'),(3.001,'No Travel')])
def test_snow_boundaries(value, level):
    assert risk(0,0,value,0)['level'] == level


@pytest.mark.parametrize('wind,load,level', [(45,30000,'Severe'),(45,30001,'No Travel'),(35,40000,'High'),(35,40001,'Severe'),(55,0,'No Travel'),(54.99,50000,'No Travel')])
def test_strict_load_rules(wind,load,level):
    assert risk(wind,0,0,load)['level'] == level


def test_missing_is_not_safe():
    assert risk(None,0,0,28000)['level'] == 'Unknown'
    assert risk(20,1.1,0,0)['level'] == 'No Travel'


def test_partial_interval_and_nonuniform_eta():
    route={'coordinates':[[0,0],[.5,0],[1,0]],'segment_distances':[25*MILE,37*MILE],'segment_durations':[3600,7200]}
    points=checkpoints(route,25,datetime(2026,10,27,tzinfo=timezone.utc))
    assert [p['mile'] for p in points] == pytest.approx([0,25,50,62])
    assert points[1]['elapsed_seconds']==3600
    assert points[2]['elapsed_seconds']==pytest.approx(3600+25/37*7200)
    assert points[-1]['elapsed_seconds']==pytest.approx(10800)
    for p in points:p['risk']=risk(0,0,0,0)
    points[-1]['risk']=risk(40,0,0,0)
    summary=summarize(points)
    assert summary['miles_by_risk']['High']==pytest.approx(12)
    assert sum(summary['miles_by_risk'].values())==pytest.approx(62)


def test_exact_multiple_no_duplicate_destination():
    r={'coordinates':[[0,0],[1,0]],'segment_distances':[50*MILE],'segment_durations':[3600]}
    assert len(checkpoints(r,25,datetime.now(timezone.utc)))==3


def candidate(id,severe=0,high=0,avg=0,seconds=3600,blocked=False,complete=True):
    return {'id':id,'duration_seconds':seconds,'summary':{'complete':complete,'blocked':blocked,'average_risk':avg,'miles_by_risk':{'Severe':severe,'High':high}}}


def test_ranking_prioritizes_severe_not_time():
    a,b=candidate('a',severe=1,seconds=100),candidate('b',severe=0,seconds=5000)
    assert recommend([a,b])[0]=='b'


def test_no_travel_cannot_win_by_low_severe_miles():
    assert recommend([candidate('a',blocked=True),candidate('b',severe=5)])[0]=='b'
    assert recommend([candidate('a',blocked=True)])[0] is None


def test_unknown_excluded_and_comparison_qualified():
    assert recommend([candidate('a',complete=False),candidate('b')])[0]=='b'
    assert 'incomplete' in recommend([candidate('a',complete=False),candidate('b')])[2]


def test_weather_interval_and_units():
    series={'hourly':{'time':['2026-10-27T12:00','2026-10-27T13:00'],'wind_speed_10m':[10,30],'rain':[0,25.4],'showers':[0,25.4],'snowfall':[0,2.54]}}
    result=at_time(series,datetime(2026,10,27,12,30,tzinfo=timezone.utc))
    assert result['wind_mph']==20
    assert result['rain_in_hr']==2
    assert result['snow_in_hr']==1
    assert at_time(series,datetime(2026,10,27,14,tzinfo=timezone.utc))['wind_mph'] is None


def test_unknown_exposure_separate():
    p=[{'id':0,'mile':0,'risk':risk(None,0,0,0)},{'id':1,'mile':10,'risk':risk(0,0,0,0)}]
    s=summarize(p)
    assert s['miles_by_risk']['Unknown']==10
    assert s['average_risk'] is None


def test_all_recommendation_tie_breakers():
    assert recommend([candidate('a',high=5,seconds=1),candidate('b',high=2,seconds=100)])[0]=='b'
    assert recommend([candidate('a',avg=2,seconds=1),candidate('b',avg=1,seconds=100)])[0]=='b'
    assert recommend([candidate('a',seconds=100),candidate('b',seconds=50)])[0]=='b'
    assert recommend([candidate('b'),candidate('a')])[0]=='a'
