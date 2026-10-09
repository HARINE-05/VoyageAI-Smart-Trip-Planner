"""Validated trip inputs and deterministic, auditable arithmetic."""
from datetime import date
from math import ceil, isfinite
from pydantic import BaseModel, Field, model_validator

DESTINATIONS = {
    'Singapore': {'country': 'Singapore', 'lat': 1.3521, 'lon': 103.8198},
    'Bangkok': {'country': 'Thailand', 'lat': 13.7563, 'lon': 100.5018},
    'Dubai': {'country': 'United Arab Emirates', 'lat': 25.2048, 'lon': 55.2708},
    'Goa': {'country': 'India', 'lat': 15.4909, 'lon': 73.8278},
}
ORIGINS = ['Chennai', 'Bengaluru', 'Mumbai', 'Delhi']
CURRENCIES = ['INR', 'USD', 'EUR', 'SGD']

class TripRequest(BaseModel):
    origin: str
    destination: str
    start: date
    end: date
    travellers: int = Field(default=1, ge=1, le=10)
    budget: float = Field(gt=0, allow_inf_nan=False)
    currency: str = 'INR'
    nationality: str = Field(default='Indian', min_length=2, max_length=60)
    interests: str = Field(default='Culture, sightseeing and local food', max_length=500)

    @model_validator(mode='after')
    def validate_trip(self):
        if self.origin not in ORIGINS or self.destination not in DESTINATIONS:
            raise ValueError('Select an origin and destination supported by the sample dataset.')
        if self.currency not in CURRENCIES:
            raise ValueError('Unsupported currency.')
        if self.start < date.today() or self.end < self.start:
            raise ValueError('Use future dates, with return on or after departure.')
        if self.days > 14:
            raise ValueError('This project supports trips of 1–14 days.')
        return self

    @property
    def days(self):
        return (self.end - self.start).days + 1

    @property
    def nights(self):
        return (self.end - self.start).days


def cost_breakdown(flight: float, hotel: float, days: int, nights: int,
                   travellers: int, food: float, transport: float, activities: float):
    values = [flight, hotel, food, transport, activities]
    if any(not isfinite(v) or v < 0 for v in values):
        raise ValueError('Costs must be finite and non-negative.')
    if not (days >= 1 and nights == days - 1 and travellers >= 1):
        raise ValueError('Invalid trip duration or traveller count.')
    items = {'Return flights': flight * travellers,
             'Hotel (2 people per room)': hotel * nights * ceil(travellers / 2),
             'Food allowance': food * days * travellers,
             'Local transport allowance': transport * days * travellers,
             'Activities allowance': activities * days * travellers}
    items['Contingency (10%)'] = sum(items.values()) * .1
    return {'items_inr': {k: round(v, 2) for k, v in items.items()},
            'total_inr': round(sum(items.values()), 2)}
