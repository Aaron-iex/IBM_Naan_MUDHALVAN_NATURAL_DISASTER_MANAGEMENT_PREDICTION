import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
import logging # Added for better logging

# --- FastAPI Imports ---
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field 

# --- Async HTTP Client ---
import httpx 

# --- Google Gemini Client ---
import google.generativeai as genai 
# Optional: Import specific Google API error types for finer handling
# from google.api_core import exceptions as google_exceptions 

# --- Add project root to path if helper files are there ---
# Adjust this path if your project structure is different
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# --- Import helper functions ---
try:
    # Assuming these helpers are synchronous for now
    from get_weather import get_city_weather
    from get_earthquakes import get_recent_earthquakes_near_location
    from get_events import get_natural_events
    from get_news import get_disaster_news
    from utils import get_coordinates # Geocoding function
except ImportError as e:
     print(f"FATAL ERROR: Could not import helper modules: {e}. Ensure they are in the Python path ({project_root}).")
     sys.exit(1) 

# --- Load Environment Variables ---
load_dotenv() 

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# FastAPI Security Key (Generate this yourself!)
API_KEY_FASTAPI = os.getenv("FASTAPI_SECRET_KEY")
if not API_KEY_FASTAPI:
    logger.critical("FATAL ERROR: FASTAPI_SECRET_KEY not found in .env. Cannot start API securely.")
    sys.exit(1) # Exit if the security key isn't set

API_KEY_NAME = "X-API-Key" 
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False) # auto_error=False allows custom error

# Default location context (Center of India approx.)
DEFAULT_LAT = 20.5937 
DEFAULT_LON = 78.9629 
INDIA_BBOX = [68, 6, 98, 38] # Approx Bounding Box for India for EONET

# --- Configure Gemini ---
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
gemini_model = None # Initialize as None
if not GOOGLE_API_KEY:
    logger.warning("Warning: GOOGLE_API_KEY not found in .env file. LLM functionality will be disabled.")
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        # Choose the Gemini model - Flash is fast and capable
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest') 
        logger.info("Gemini configured successfully using model 'gemini-1.5-flash-latest'.")
    except Exception as e:
        logger.error(f"Error configuring Gemini: {e}. LLM functionality will be disabled.")
        gemini_model = None # Ensure it's None if config fails

# --- Security Dependency ---
async def get_api_key(key: str = Security(api_key_header)):
    """Dependency function to validate the API key."""
    if key is None:
        logger.warning("API Key missing.")
        raise HTTPException(status_code=401, detail="API Key required")
    if key == API_KEY_FASTAPI:
        return key
    else:
        logger.warning("Invalid API Key received.")
        raise HTTPException(status_code=401, detail="Invalid API Key")

# --- FastAPI App Initialization ---
# Add description and versioning
# Apply API key security globally using the dependency
app = FastAPI(
    title="Disaster Management Assistant API",
    description="Provides weather, disaster context (earthquakes, events, news) and LLM-powered assistance.",
    version="1.1.0", # Incremented version
    dependencies=[Depends(get_api_key)] 
)

# --- Pydantic Models for Request/Response Validation ---
# (Keep models from previous version: WeatherQuery, EarthquakeQuery, EventQuery, NewsQuery, ProcessQuery)
class WeatherQuery(BaseModel):
    city: str = Field(..., example="Mumbai")

class EarthquakeQuery(BaseModel):
    latitude: float = Field(default=DEFAULT_LAT, example=28.61)
    longitude: float = Field(default=DEFAULT_LON, example=77.23)
    radius_km: int = Field(default=1000, gt=0, example=1000) # Greater than 0
    days: int = Field(default=7, ge=1, le=90, example=7) # 1 to 90 days
    min_magnitude: float = Field(default=4.0, ge=0, example=4.0)

class EventQuery(BaseModel):
    category: str | None = Field(default=None, example="severeStorms") 
    days: int = Field(default=7, ge=1, le=90, example=7)
    # Example: bbox: list[float] | None = Field(default=None, example=[68, 6, 98, 38])

class NewsQuery(BaseModel):
    search_query: str = Field(..., example="India flood OR cyclone")
    page_size: int = Field(default=5, ge=1, le=20, example=5) # Limit page size

class ProcessQuery(BaseModel):
    text_input: str = Field(..., example="What are the risks from Cyclone Remal in Kolkata?")
    location_context: str | None = Field(default=None, example="Kolkata") 
    max_new_tokens: int = Field(default=300, ge=50, le=1024, example=300) # Reasonable token limits


# --- API Endpoints ---

@app.get("/", tags=["Status"], summary="Check API Status", dependencies=[]) # Allow status check without key
async def read_root():
    """Returns a simple message indicating the API is running."""
    logger.info("Root endpoint '/' accessed.")
    return {"message": "Disaster Management Assistant API is running."}

# --- Context Endpoints (Optional Direct Access) ---
# These remain synchronous as they call the synchronous helper functions directly

@app.post("/context/weather", tags=["Context APIs"], summary="Get Current Weather")
async def fetch_weather_direct(query: WeatherQuery):
    """Fetches current weather for a specified city using OpenWeatherMap."""
    logger.info(f"Fetching weather for city: {query.city}")
    weather_data = get_city_weather(query.city) # Synchronous call
    if "error" in weather_data:
        error_detail = f"Weather Error: {weather_data['error']}"
        logger.error(error_detail)
        # Use appropriate status codes
        if "API Key" in weather_data["error"]:
             raise HTTPException(status_code=500, detail=f"Weather API Configuration Error: {weather_data['error']}")
        elif "404" in str(weather_data["error"]): # Basic check for city not found
             raise HTTPException(status_code=404, detail=f"Weather Error: City '{query.city}' not found.")
        else:
             raise HTTPException(status_code=400, detail=error_detail)
    logger.info(f"Successfully fetched weather for {query.city}")
    return weather_data

@app.post("/context/earthquakes", tags=["Context APIs"], summary="Get Recent Earthquakes")
async def fetch_earthquakes_direct(query: EarthquakeQuery):
    """Fetches recent earthquakes near a location from USGS."""
    logger.info(f"Fetching earthquakes near ({query.latitude}, {query.longitude})")
    quakes = get_recent_earthquakes_near_location( # Synchronous call
        query.latitude, query.longitude, query.radius_km, query.days, query.min_magnitude
    )
    if "error" in quakes:
        error_detail = f"Earthquake API Error: {quakes['error']}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    logger.info(f"Found {quakes.get('count', 0)} earthquakes.")
    return quakes

@app.post("/context/natural_events", tags=["Context APIs"], summary="Get Natural Events")
async def fetch_events_direct(query: EventQuery):
    """Fetches recent natural events from NASA EONET."""
    logger.info(f"Fetching EONET events (Category: {query.category}, Days: {query.days})")
    events = get_natural_events(days=query.days, category=query.category, bbox=INDIA_BBOX) # Synchronous call
    if "error" in events:
        error_detail = f"EONET API Error: {events['error']}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    logger.info(f"Found {events.get('count', 0)} EONET events.")
    return events

@app.post("/context/news", tags=["Context APIs"], summary="Get Disaster News")
async def fetch_news_direct(query: NewsQuery):
    """Fetches relevant news articles from NewsAPI."""
    logger.info(f"Fetching news for query: '{query.search_query}'")
    news = get_disaster_news(query=query.search_query, page_size=query.page_size) # Synchronous call
    if "error" in news:
        error_detail = f"NewsAPI Error: {news['error']}"
        logger.error(error_detail)
        if "API Key" in news["error"]:
             raise HTTPException(status_code=500, detail=f"NewsAPI Configuration Error: {news['error']}")
        else:
             raise HTTPException(status_code=400, detail=error_detail)
    logger.info(f"Found {news.get('total_results', 0)} news articles.")
    return news

# --- Main LLM Processing Endpoint ---

@app.post("/process", tags=["LLM Assistant"], summary="Process query with context")
async def process_with_llm_context(query: ProcessQuery):
    """
    Processes text input by asynchronously gathering context (weather, earthquakes, 
    events, news) based on optional location, constructs a detailed prompt, 
    and queries the configured Gemini LLM.
    """
    request_start_time = datetime.now()
    logger.info(f"Processing request for query: '{query.text_input[:50]}...', Location: {query.location_context}")

    if not gemini_model: # Check if Gemini was configured successfully
        logger.error("LLM endpoint called but Gemini model is not configured.")
        raise HTTPException(status_code=503, detail="LLM Service (Gemini) is not configured or unavailable.")

    # --- 1. Determine Location for Context ---
    context_data = {}
    target_lat, target_lon = DEFAULT_LAT, DEFAULT_LON
    location_name_for_context = "India (default)"
    location_detail = f"Default location ({DEFAULT_LAT:.2f}, {DEFAULT_LON:.2f})"

    if query.location_context:
        logger.info(f"Geocoding location context: '{query.location_context}'")
        coords = get_coordinates(query.location_context) # This helper is synchronous
        if "latitude" in coords:
            target_lat, target_lon = coords["latitude"], coords["longitude"]
            location_name_for_context = query.location_context
            location_detail = f"{location_name_for_context} ({target_lat:.2f}, {target_lon:.2f})"
            logger.info(f"Geocoding successful: {location_detail}")
        else:
            logger.warning(f"Geocoding failed for '{query.location_context}'. Using default location.")
            location_detail = f"Default location ({DEFAULT_LAT:.2f}, {DEFAULT_LON:.2f}) (Geocoding failed for: {query.location_context})"
    context_data["location_info"] = location_detail


    # --- 2. Gather Context Asynchronously using httpx ---
    # Note: The underlying helper functions are still synchronous in this example.
    # For true async I/O, the helper functions (get_weather, get_earthquakes etc.) 
    # would need to be rewritten using httpx internally.
    # This structure shows HOW you would orchestrate if they were async.
    
    async def fetch_all_context():
        # Use a single httpx client for potential future async helpers
        async with httpx.AsyncClient() as client: 
            # --- Weather ---
            weather_info = None
            if query.location_context and "Geocoding failed" not in context_data["location_info"]:
                try:
                    # Simulating async call even though helper is sync
                    weather_data = get_city_weather(location_name_for_context) 
                    if "error" not in weather_data:
                        weather_info = f"In {weather_data.get('city', location_name_for_context)}: {weather_data.get('temperature_c')}C, {weather_data.get('description')}, Humidity {weather_data.get('humidity_pct')}%, Wind {weather_data.get('wind_speed_mps')} m/s."
                    else:
                        logger.warning(f"Failed to get weather for {location_name_for_context}: {weather_data['error']}")
                except Exception as e:
                     logger.error(f"Exception fetching weather: {e}")
            
            # --- Earthquakes ---
            quake_info = None
            try:
                # Simulating async call
                quakes = get_recent_earthquakes_near_location(target_lat, target_lon, radius_km=1500, days=7, min_magnitude=4.0)
                if "error" not in quakes and quakes.get("count", 0) > 0:
                    quake_summary = "; ".join([f"Mag {q['magnitude']} near {q['place']} ({q['time_utc'][:16]}Z)" for q in quakes['earthquakes'][:3]]) # Top 3
                    quake_info = quake_summary
            except Exception as e:
                 logger.error(f"Exception fetching earthquakes: {e}")

            # --- Natural Events (EONET) ---
            event_info = None
            try:
                # Simulating async call
                events = get_natural_events(days=10, bbox=INDIA_BBOX, limit=5) # Last 10 days, India region
                if "error" not in events and events.get("count", 0) > 0:
                    event_summary = "; ".join([f"{e['category']}: {e['title']} (Updated {e['last_update_utc'][:10]})" for e in events['events']])
                    event_info = event_summary
            except Exception as e:
                 logger.error(f"Exception fetching EONET events: {e}")

            # --- News ---
            news_info = None
            try:
                # Simulating async call
                # Create a slightly more focused query
                news_query_terms = f"({query.text_input[:80]}) AND ({location_name_for_context if query.location_context else 'India'}) AND (disaster OR flood OR cyclone OR earthquake OR heatwave OR landslide)"
                news = get_disaster_news(query=news_query_terms, page_size=3)
                if "error" not in news and news.get("total_results", 0) > 0:
                    news_summary = "; ".join([f"'{n['title']}' ({n['source']})" for n in news['articles']])
                    news_info = news_summary
            except Exception as e:
                 logger.error(f"Exception fetching news: {e}")

            # --- Compile results ---
            return {
                "current_weather": weather_info,
                "recent_earthquakes": quake_info,
                "recent_natural_events": event_info,
                "related_news_headlines": news_info,
            }

    logger.info("Gathering context...")
    context_gathering_start = datetime.now()
    fetched_context = await fetch_all_context()
    context_gathering_duration = (datetime.now() - context_gathering_start).total_seconds()
    logger.info(f"Context gathering took {context_gathering_duration:.2f} seconds.")
    context_data.update(fetched_context) # Add fetched data to overall context

    # --- 3. Construct the Prompt for the LLM ---
    context_lines = [f"- {key.replace('_', ' ').title()}: {value}" for key, value in context_data.items() if value and key != 'location_info'] 
    context_string = "\n".join(context_lines)
    
    # Define the prompt structure clearly for the LLM
    final_prompt = f"""Role: You are an AI assistant specialized in Indian disaster management and safety procedures.
Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}
Location Context: {context_data.get("location_info", "Default India context")}

Relevant Real-time Information:
{context_string if context_string else "No specific real-time context was retrieved for this query."}

User's Request: {query.text_input}

Task: Based ONLY on the provided real-time information and your general knowledge of disaster management best practices relevant to India, respond directly and accurately to the user's request. If providing safety advice, make it clear, concise, and actionable. If context is missing for a specific aspect of the query, state that clearly but still provide general advice if possible. Prioritize safety.
Response:"""

    logger.info(f"Constructed prompt for LLM (length: {len(final_prompt)} chars). Sending to Gemini...")
    # Uncomment to log the full prompt for debugging (can be long)
    # logger.debug(f"Full prompt:\n{final_prompt}") 

    # --- 4. Call the LLM (Gemini Example using Async SDK) ---
    llm_call_start = datetime.now()
    generated_text = "Error: LLM call failed." # Default error message
    try:
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=query.max_new_tokens,
            temperature=0.6, # Slightly lower temperature for more factual/advice-oriented response
            # top_p=0.95, # Optional parameter
            # top_k=40,   # Optional parameter
        )
        
        # Use the async version of the Gemini client call
        llm_response = await gemini_model.generate_content_async(
            final_prompt, 
            generation_config=generation_config,
            # Consider adding safety_settings if needed:
            # safety_settings=[
            #     {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            #     {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            #     # Add other categories as needed
            # ]
        )
        
        llm_call_duration = (datetime.now() - llm_call_start).total_seconds()
        
        # --- Process LLM Response ---
        # Check for safety blocks or empty responses
        if not llm_response.candidates:
             logger.warning("LLM response blocked or empty candidates list.")
             if llm_response.prompt_feedback.block_reason:
                  generated_text = f"Response blocked by safety filter: {llm_response.prompt_feedback.block_reason}"
             else:
                  generated_text = "LLM response was empty or blocked for unknown reasons."
             raise HTTPException(status_code=400, detail=generated_text) # Raise error for blocked content

        else:
             # Access the text content safely
             try:
                generated_text = llm_response.text
                logger.info(f"LLM call successful ({llm_call_duration:.2f} seconds). Response length: {len(generated_text)} chars.")
             except ValueError as ve:
                # Handle cases where accessing .text might fail (e.g., function calls in future)
                logger.error(f"Error accessing LLM response text: {ve}. Response parts: {llm_response.parts}")
                generated_text = "Error: Could not parse LLM response content."
                raise HTTPException(status_code=500, detail=generated_text)

    except Exception as e:
        llm_call_duration = (datetime.now() - llm_call_start).total_seconds()
        logger.error(f"Error during Gemini API call or processing ({llm_call_duration:.2f} seconds): {e}", exc_info=True) # Log traceback
        # Check for specific Google API errors if needed
        # if isinstance(e, google_exceptions.GoogleAPIError): ...
        raise HTTPException(status_code=502, detail=f"Error communicating with the LLM service: {e}")

    total_request_duration = (datetime.now() - request_start_time).total_seconds()
    logger.info(f"Total request processing time: {total_request_duration:.2f} seconds.")

    # --- Return the final response ---
    return {
        "user_query": query.text_input,
        "location_context_provided": query.location_context,
        "context_used_summary": context_data, # Return the context summary used in the prompt
        "llm_response": generated_text
    }

# --- Optional: Run instruction for local testing ---
if __name__ == "__main__":
    import uvicorn
    print("--- Starting Disaster Management Assistant API Locally ---")
    print(f"Python version: {sys.version}")
    print(f"FastAPI version: {FastAPI().version}") # Requires fastapi install
    # Check if critical components loaded
    if not API_KEY_FASTAPI:
         print("CRITICAL ERROR: FastAPI secret key (FASTAPI_SECRET_KEY) not set in .env. Exiting.")
         sys.exit(1)
    else:
         print("FastAPI secret key loaded.")
         
    if not gemini_model:
         print("WARNING: Gemini model not configured (check GOOGLE_API_KEY in .env). LLM endpoints will fail.")
    else:
         print("Gemini model configured.")
         
    print("\nMake sure all required API keys (OpenWeatherMap, NewsAPI) are also in the .env file.")
    print(f"Starting Uvicorn server on http://127.0.0.1:8000")
    print("Access API documentation at http://127.0.0.1:8000/docs")
    print("Press CTRL+C to stop the server.")
    
    # Run the server
    uvicorn.run(
        "main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True, # Enable auto-reload for development
        log_level="info" # Set uvicorn log level
        )
    
    # --- End of Local Testing ---