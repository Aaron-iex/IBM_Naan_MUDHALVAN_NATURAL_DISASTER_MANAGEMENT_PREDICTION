# get_earthquakes.py
import requests
from datetime import datetime, timedelta
import geopy.distance # To calculate distance

# USGS API endpoint for significant earthquakes in the last N days (example)
#Customize parameters: https://earthquake.usgs.gov/fdsnws/event/1/
USGS_BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

def get_recent_earthquakes_near_location(lat, lon, radius_km=500, days=7, min_magnitude=4.0):
    """
    Fetches recent significant earthquakes near a specific lat/lon.
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)

    params = {
        'format': 'geojson',
        'starttime': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
        'endtime': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
        'latitude': lat,
        'longitude': lon,
        'maxradiuskm': radius_km,
        'minmagnitude': min_magnitude,
        'orderby': 'time' # Most recent first
    }

    try:
        response = requests.get(USGS_BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        earthquakes = []
        for feature in data.get('features', []):
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            coords = geom.get('coordinates', [None, None])

            quake_lat = coords[1]
            quake_lon = coords[0]

            if quake_lat is not None and quake_lon is not None:
                 # Optional: Calculate distance if API didn't filter perfectly (though maxradiuskm should handle it)
                 # distance = geopy.distance.geodesic((lat, lon), (quake_lat, quake_lon)).km
                 earthquakes.append({
                    'id': feature.get('id'),
                    'magnitude': props.get('mag'),
                    'place': props.get('place'),
                    'time_utc': datetime.utcfromtimestamp(props.get('time') / 1000).isoformat() if props.get('time') else None,
                    'latitude': quake_lat,
                    'longitude': quake_lon,
                    'depth_km': coords[2],
                    'tsunami_warning': bool(props.get('tsunami', 0)),
                    'details_url': props.get('url')
                 })
        return {"count": len(earthquakes), "earthquakes": earthquakes}

    except requests.exceptions.RequestException as e:
        print(f"Error fetching USGS data: {e}")
        return {"error": f"Network error fetching earthquake data: {e}"}
    except Exception as e:
        print(f"Error processing USGS data: {e}")
        return {"error": f"Error processing earthquake data: {e}"}

if __name__ == "__main__":
    # Example: Delhi coordinates approx 28.61 N, 77.23 E
    delhi_lat, delhi_lon = 13.08, 780.27
    quakes = get_recent_earthquakes_near_location(delhi_lat, delhi_lon, radius_km=1000, days=30, min_magnitude=4.0)
    import json
    print(json.dumps(quakes, indent=2))