"""Geocode a street address with the Google Maps Geocoding API."""
import os
import sys

import requests
from dotenv import load_dotenv


def geocode(address):
    load_dotenv()
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("Set GOOGLE_MAPS_API_KEY in your .env file first.")
    response = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": api_key}, timeout=15,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("status") != "OK" or not result.get("results"):
        raise ValueError(f"Google Geocoding API returned {result.get('status', 'no result')}.")
    location = result["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


if __name__ == "__main__":
    search_address = " ".join(sys.argv[1:]) or "IIM Ahmedabad, Gujarat"
    latitude, longitude = geocode(search_address)
    print(f"{search_address}: latitude={latitude}, longitude={longitude}")
