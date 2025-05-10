# utils.py
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# Initialize geocoder with a unique user agent (required by Nominatim policy)
geolocator = Nominatim(user_agent="disaster_management_app_v1_{int(time.time())}") 
# Apply rate limiting (max 1 request per second)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def get_coordinates(place_name):
    """ Gets latitude and longitude for a place name using OpenStreetMap Nominatim. """
    try:
        location = geocode(place_name)
        if location:
            return {"latitude": location.latitude, "longitude": location.longitude}
        else:
            return {"error": f"Could not geocode '{place_name}'."}
    except Exception as e:
        print(f"Geocoding error for '{place_name}': {e}")
        return {"error": f"Geocoding failed for '{place_name}': {e}"}

if __name__ == "__main__":
    coord_delhi = get_coordinates("Delhi, India")
    print(f"Delhi: {coord_delhi}")
    coord_mumbai = get_coordinates("Mumbai")
    print(f"Mumbai: {coord_mumbai}")
    coord_unknown = get_coordinates("UnknownPlaceXYZ")
    print(f"UnknownPlaceXYZ: {coord_unknown}")