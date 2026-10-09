from datetime import date, timedelta
from unittest.mock import Mock
import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from trip.core import TripRequest, cost_breakdown
from trip.agents import run_trip, react_itinerary
from trip.rag import KnowledgeBase
from trip.tools import get_weather_forecast
from trip.mcp_client import call_batch


def request(**overrides):
    values = dict(origin='Chennai', destination='Singapore', start=date.today()+timedelta(days=7),
                  end=date.today()+timedelta(days=10), budget=80000)
    return TripRequest(**(values | overrides))


def test_costs_include_rooms_and_group_size():
    result = cost_breakdown(10000, 2000, 4, 3, 3, 500, 200, 100)
    assert result['items_inr']['Hotel (2 people per room)'] == 12000
    assert result['total_inr'] == 56760


def test_input_validation():
    for overrides in [{'budget':0}, {'budget':float('nan')}, {'travellers':0},
                      {'end':date.today()}, {'origin':'Unknown'}, {'currency':'XXX'},
                      {'end':date.today()+timedelta(days=25)}]:
        with pytest.raises(ValueError):
            request(**overrides)


def test_rag_retrieves_destination_with_citation():
    for city in ['Singapore','Bangkok','Dubai','Goa']:
        docs = KnowledgeBase().search(f'{city} Indian visa destination insurance')
        assert any(city in d['title'] and d['kind']=='destination' for d in docs)
        assert all(d['id'] and d['url'] for d in docs)


def test_weather_outside_window_does_not_invent_forecast():
    result = get_weather_forecast.invoke({'city':'Singapore','start':str(date.today()+timedelta(days=90)),
                                         'end':str(date.today()+timedelta(days=93)), 'demo':False})
    assert result['status'] == 'unavailable'
    assert 'daily' not in result


def test_real_mcp_transport_all_three_tools():
    results = call_batch([
        ('search_flights', {'origin':'Chennai','destination':'Singapore','departure':'2027-01-01','return_date':'2027-01-04'}),
        ('search_hotels', {'city':'Singapore'}),
        ('convert_currency', {'amount':6500,'from_currency':'INR','to_currency':'SGD','demo':True})])
    assert results[0]['options'][0]['return_fare_inr'] == 24000
    assert len(results[1]['options']) == 3
    assert results[2]['amount'] == 100


def test_demo_happy_path():
    result = run_trip(request())
    assert not result['over_budget']
    assert result['revision'] == 0
    assert len(result['trace']) == 5
    assert 'Day 4' in result['summary']
    assert result['costs']['total_inr'] == 63470


def test_budget_feedback_can_find_cheaper_plan():
    result = run_trip(request(budget=50000))
    assert result['revision'] == 1
    assert not result['over_budget']
    assert result['hotel']['tier'] == 'economy'


def test_impossible_budget_stops_after_two_revisions():
    result = run_trip(request(budget=1000))
    assert result['revision'] == 2
    assert result['over_budget']
    assert 'Over budget' in result['summary']
    assert sum(x['agent']=='Planner' for x in result['trace']) == 3


def test_non_inr_and_same_day():
    r = request(end=date.today()+timedelta(days=7), currency='SGD', budget=1000)
    result = run_trip(r)
    assert result['costs']['items_inr']['Hotel (2 people per room)'] == 0
    assert result['conversion']['currency'] == 'SGD'


def test_live_mode_requires_keys(monkeypatch):
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    with pytest.raises(ValueError, match='GOOGLE_API_KEY'):
        run_trip(request(), demo=False)


def test_react_observes_tools_and_honours_iteration_cap():
    @tool
    def echo(value: str) -> str:
        """Echo a test value."""
        return value
    llm = Mock()
    llm.bind_tools.return_value.invoke.return_value = AIMessage(content='', tool_calls=[
        {'name':'echo','args':{'value':'observed'},'id':'test-call','type':'tool_call'}])
    llm.invoke.return_value = AIMessage(content='Finished with available evidence.')
    output, observations, actions = react_itinerary(llm, 'Plan', [echo], max_rounds=5)
    assert len(observations) == 5
    assert all(x['output']=='observed' for x in observations)
    assert llm.bind_tools.return_value.invoke.call_count == 5
    assert llm.invoke.call_count == 1
    assert 'limit' in actions[-1]
    assert output.startswith('Finished')


def test_streamlit_form_and_results():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
    assert not app.exception
    next(b for b in app.button if b.label == 'Create my travel plan').click().run(timeout=30)
    assert not app.exception
    assert len(app.metric) == 3
    assert app.metric[2].value == 'Within estimate'
