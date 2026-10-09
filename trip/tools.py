import json
import hashlib
import os
from datetime import date, timedelta
import requests
from langchain_core.tools import tool
from trip.core import DESTINATIONS, cost_breakdown
from trip.rag import KnowledgeBase

@tool
def calculate_trip_cost(flight: float, hotel: float, days: int, nights: int,
                        travellers: int, food: float, transport: float, activities: float) -> dict:
    """Calculate group trip cost in INR including hotel rooms and a 10 percent reserve."""
    return cost_breakdown(flight, hotel, days, nights, travellers, food, transport, activities)

@tool
def get_weather_forecast(city: str, start: str, end: str, demo: bool = False) -> dict:
    """Get Open-Meteo daily rain and temperatures only within its 16-day forecast window."""
    if city not in DESTINATIONS:
        return {'status': 'unavailable', 'reason': 'Unsupported destination.'}
    if demo:
        return {'status': 'demo', 'note': 'No real forecast requested. Keep an indoor alternative each day.'}
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first < date.today() or last > date.today() + timedelta(days=15):
        return {'status': 'unavailable', 'reason': 'Trip falls outside the 16-day forecast window. Check closer to departure.'}
    loc = DESTINATIONS[city]
    try:
        r = requests.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude': loc['lat'], 'longitude': loc['lon'], 'timezone': 'auto',
            'start_date': start, 'end_date': end,
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max'}, timeout=20)
        r.raise_for_status()
        return {'status': 'live', 'source': 'https://open-meteo.com/', 'daily': r.json()['daily']}
    except (requests.RequestException, ValueError, KeyError):
        return {'status': 'unavailable', 'reason': 'Weather service could not be reached. No forecast assumed.'}

@tool
def retrieve_guides(query: str) -> str:
    """Retrieve local destination/visa/insurance guidance with stable citation IDs."""
    return json.dumps(KnowledgeBase().search(query))

@tool
def tavily_search(query: str) -> str:
    """Search current events, closures and official travel guidance; return source URLs."""
    key = os.getenv('TAVILY_API_KEY', '')
    if not key:
        return json.dumps({'status': 'unavailable', 'reason': 'TAVILY_API_KEY is missing.'})
    try:
        r = requests.post('https://api.tavily.com/search', headers={'Authorization': f'Bearer {key}'},
                          json={'query': query, 'max_results': 5, 'search_depth': 'basic',
                                'include_answer': False}, timeout=25)
        r.raise_for_status()
        return json.dumps({'status': 'live', 'results': [
            {'id': 'WEB-' + hashlib.sha256(x['url'].encode()).hexdigest()[:8], 'title': x['title'], 'url': x['url'], 'text': x['content'][:1800]}
            for i, x in enumerate(r.json().get('results', []))]})
    except (requests.RequestException, ValueError, KeyError):
        return json.dumps({'status': 'unavailable', 'reason': 'Tavily request failed. No current advisories verified.'})
