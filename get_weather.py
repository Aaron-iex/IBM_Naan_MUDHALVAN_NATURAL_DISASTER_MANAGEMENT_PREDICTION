# get_weather.py
import requests
import os
from dotenv import load_dotenv

load_dotenv() # Load variables from .env file

API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
BASE_URL = "http://api.openweathermap.org/data/2.5/weather?"

def get_city_weather(city_name):
    if not API_KEY:
        return {"error": "OpenWeatherMap API Key not found in .env file"}

    complete_url = f"{BASE_URL}appid={API_KEY}&q={city_name}&units=metric" # Use metric units (Celsius)

    try:
        response = requests.get(complete_url)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        weather_data = response.json()

        if weather_data.get("cod") != 200:
             return {"error": f"OWM API Error: {weather_data.get('message', 'Unknown error')}"}

        # Extract relevant info (example)
        main = weather_data.get("main", {})
        wind = weather_data.get("wind", {})
        weather_desc = weather_data.get("weather", [{}])[0].get("description", "N/A")

        report = {
            "city": weather_data.get("name"),
            "temperature_c": main.get("temp"),
            "feels_like_c": main.get("feels_like"),
            "humidity_pct": main.get("humidity"),
            "pressure_hpa": main.get("pressure"),
            "wind_speed_mps": wind.get("speed"),
            "description": weather_desc,
            "raw_data": weather_data # Include raw data if needed
        }
        return report

    except requests.exceptions.RequestException as e:
        return {"error": f"Network or request error: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}

if __name__ == "__main__":
    city = "Mumbai" # Example City
    weather_report = get_city_weather(city)

    if "error" in weather_report:
        print(f"Error fetching weather for {city}: {weather_report['error']}")
    else:
        print(f"Weather Report for {weather_report['city']}:")
        print(f"- Temperature: {weather_report['temperature_c']}°C (Feels like: {weather_report['feels_like_c']}°C)")
        print(f"- Humidity: {weather_report['humidity_pct']}%")
        print(f"- Wind Speed: {weather_report['wind_speed_mps']} m/s")
        print(f"- Conditions: {weather_report['description']}")
        # print("\nRaw Data:")
        import json
        # print(json.dumps(weather_report['raw_data'], indent=2))``