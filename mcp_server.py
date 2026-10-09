"""Custom MCP server: started automatically by the app over stdio."""
import json
from datetime import date
from pathlib import Path
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('Smart Trip Travel Tools')
DATA = json.loads((Path(__file__).parent / 'data/catalog.json').read_text())

@mcp.tool()
def search_flights(origin: str, destination: str, departure: str, return_date: str) -> dict:
    """Find MOCK round-trip fares in INR per person; no live availability."""
    if date.fromisoformat(return_date) < date.fromisoformat(departure):
        raise ValueError('Return must follow departure.')
    options = [r for r in DATA['flights'] if r['origin'] == origin and r['destination'] == destination]
    return {'mock': True, 'departure': departure, 'return_date': return_date,
            'note': 'Synthetic classroom fares; not date-sensitive or bookable.', 'options': options}

@mcp.tool()
def search_hotels(city: str) -> dict:
    """Find MOCK hotels; rates in INR per room/night, maximum two people/room."""
    return {'mock': True, 'options': [r for r in DATA['hotels'] if r['city'] == city]}

@mcp.tool()
def convert_currency(amount: float, from_currency: str, to_currency: str, demo: bool = False) -> dict:
    """Convert money using dated Frankfurter reference rates, or labelled demo rates."""
    if amount < 0:
        raise ValueError('Amount must be non-negative.')
    supported = {'INR', 'USD', 'EUR', 'SGD'}
    if from_currency not in supported or to_currency not in supported:
        raise ValueError('Unsupported currency.')
    if from_currency == to_currency:
        rate, as_of, source = 1.0, date.today().isoformat(), 'Identity conversion'
    elif demo:
        inr_per_unit = {'INR': 1, 'USD': 85, 'EUR': 95, 'SGD': 65}
        rate = inr_per_unit[from_currency] / inr_per_unit[to_currency]
        as_of, source = 'synthetic', 'DEMO fixed rates; not current market rates'
    else:
        response = requests.get('https://api.frankfurter.dev/v1/latest',
                                params={'base': from_currency, 'symbols': to_currency}, timeout=20)
        response.raise_for_status()
        body = response.json()
        rate, as_of, source = body['rates'][to_currency], body['date'], 'Frankfurter reference rate'
    return {'amount': round(amount * rate, 2), 'rate': rate, 'currency': to_currency,
            'as_of': as_of, 'source': source}

if __name__ == '__main__':
    mcp.run(transport='stdio')
