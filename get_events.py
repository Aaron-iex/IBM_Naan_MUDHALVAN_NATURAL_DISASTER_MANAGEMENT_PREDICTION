# get_events.py
import requests
from datetime import datetime, timedelta

# NASA EONET API - v3 Layers endpoint (e.g., severe storms, wildfires)
# See categories: https://eonet.gsfc.nasa.gov/docs/v3#categories
EONET_API_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"

def get_natural_events(days=7, category=None, status="open", limit=20, bbox=None):
    """
    Fetches recent/ongoing natural events from NASA EONET.
    bbox format: [lon_min, lat_min, lon_max, lat_max] for specific area (e.g., India)
    Example India bbox (approx): [68, 6, 98, 38]
    """
    params = {
        'status': status, # 'open' for ongoing, can also use 'closed'
        'days': days,     # Look back N days for events *updated* within this period
        'limit': limit,   # Max number of events
    }
    if category:
        params['category'] = category # E.g., 'severeStorms', 'wildfires', 'volcanoes'
    if bbox and len(bbox) == 4:
         params['bbox'] = ",".join(map(str, bbox))

    try:
        response = requests.get(EONET_API_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        events = []
        for event in data.get('events', []):
             # Get latest geometry point (often the location)
             last_geom = event.get('geometry', [{}])[-1]
             coords = last_geom.get('coordinates')
             lat, lon = (coords[1], coords[0]) if coords and len(coords) == 2 else (None, None)

             events.append({
                'id': event.get('id'),
                'title': event.get('title'),
                'category': event.get('categories', [{}])[0].get('id'),
                'last_update_utc': event.get('geometry', [{}])[-1].get('date'), # Date of last update/point
                'latitude': lat,
                'longitude': lon,
                'link': event.get('link')
             })
        return {"count": len(events), "events": events}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching EONET data: {e}")
        return {"error": f"Network error fetching natural event data: {e}"}
    except Exception as e:
        print(f"Error processing EONET data: {e}")
        return {"error": f"Error processing natural event data: {e}"}

if __name__ == "__main__":
    # Example: Get open severe storms and wildfires in/near India updated in last 14 days
    india_bbox = [68, 6, 98, 38] 
    storms = get_natural_events(days=14, category='severeStorms', bbox=india_bbox)
    fires = get_natural_events(days=14, category='wildfires', bbox=india_bbox)

    import json
    print("--- Recent Storms (India Box) ---")
    print(json.dumps(storms, indent=2))
    print("\n--- Recent Wildfires (India Box) ---")
    print(json.dumps(fires, indent=2))