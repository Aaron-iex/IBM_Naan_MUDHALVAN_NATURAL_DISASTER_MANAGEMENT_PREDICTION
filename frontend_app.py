# frontend_app.py
import streamlit as st
import requests
import os
from dotenv import load_dotenv
import json # For displaying JSON context nicely

# --- Define default coordinates for frontend use ---
DEFAULT_LAT = 20.5937 # Example India center Lat
DEFAULT_LON = 78.9629 # Example India center Lon

# --- Load environment variables ---
# This tries to find .env in the script's directory, then in the parent directory (project root)
# Ensure your .env file is in one of these locations.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env') 
if not os.path.exists(dotenv_path):
    # If frontend_app.py is in a subfolder like 'frontend', this goes up one level
    project_root_for_env = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root_for_env, '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    # print(f"Loaded .env file from: {dotenv_path}") # For debugging .env loading
else:
    print(f"Warning: .env file not found at {dotenv_path} or its parent. API keys might be missing.")


# --- Configuration ---
# For local testing, this should be the address of your FastAPI backend
BACKEND_API_URL = os.getenv("DEPLOYED_FASTAPI_URL", "http://127.0.0.1:8000") 
FASTAPI_API_KEY = os.getenv("FASTAPI_SECRET_KEY") 

st.set_page_config(page_title="Disaster Management Assistant", layout="wide", initial_sidebar_state="expanded")
st.title("🌍 Disaster Management & Context Assistant")
st.markdown("Ask questions about potential disaster risks, safety procedures, or current conditions. Provide an optional location for more specific context.")

if not FASTAPI_API_KEY:
    st.error("CRITICAL ERROR: FASTAPI_SECRET_KEY is not set. Cannot communicate with the backend API. Please check your .env file and its location.")
    # print(f"DEBUG: FASTAPI_SECRET_KEY is None or empty. Check .env loading from {dotenv_path}") # Debug .env
else:
    # Prepare headers for API requests
    headers = {"X-API-Key": FASTAPI_API_KEY, "Content-Type": "application/json"}

    # --- Main User Interaction ---
    st.subheader("Ask the Assistant")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        user_query = st.text_area("Your Question or Request:", height=100, 
                                  placeholder="e.g., What are the risks of heavy rain in Mumbai?\nWhat are safety procedures for an earthquake?\nTell me about recent cyclones in India.")
    with col2:
        location_context = st.text_input("Location Context (Optional):", 
                                         placeholder="e.g., Mumbai, Delhi, Kerala")

    if st.button("🚀 Get Assistance", type="primary", use_container_width=True):
        if user_query:
            # --- Corrected Endpoint Name ---
            process_endpoint = f"{BACKEND_API_URL}/process" 
            
            payload = {
                "text_input": user_query,
                "location_context": location_context if location_context else None,
                "max_new_tokens": 350 
            }
            
            st.info(f"Attempting to connect to backend at: {process_endpoint}") # Debugging line
            try:
                with st.spinner("🔍 Gathering context and generating response... Please wait."):
                    response = requests.post(process_endpoint, headers=headers, json=payload, timeout=120) 
                
                if response.status_code == 200:
                    result = response.json()
                    st.markdown("---")
                    st.subheader("💡 Assistant's Response:")
                    st.markdown(result.get("llm_response", "No response text found from the assistant."))

                    with st.expander("View Context Used by AI & Raw Data", expanded=False):
                        st.write("**Location Provided by User:**", result.get("location_context_provided", "N/A"))
                        st.write("**Context Summary Used for LLM Prompt:**")
                        st.json(result.get("context_used_summary", {}))
                
                elif response.status_code == 401: # Unauthorized
                    st.error("🚫 Authorization Error: Invalid or missing API Key for backend access. The key provided by the frontend was rejected by the backend. Check your FASTAPI_SECRET_KEY in .env and ensure it matches what the backend expects.")
                else: # Other HTTP errors
                    st.error(f"⚠️ Error communicating with backend API: Status Code {response.status_code}")
                    try:
                        error_detail = response.json().get('detail', response.text)
                        st.error(f"Backend Error Detail: {error_detail}")
                    except Exception:
                        st.error(f"Raw Backend Error: {response.text}")

            except requests.exceptions.Timeout:
                 st.error("⏳ Error: The request to the backend API timed out. The server might be busy or the task is taking too long.")
            except requests.exceptions.ConnectionError as e: # This is the error you were seeing
                 st.error(f"🔗 Connection Error: Could not connect to the backend API at {BACKEND_API_URL}. "
                          f"**Is the backend server (FastAPI with Uvicorn) running on port 8000?** Detail: {e}")
            except requests.exceptions.RequestException as e:
                st.error(f"🚨 An API request error occurred: {e}")
            except Exception as e:
                st.error(f"💥 An unexpected error occurred in the frontend: {e}")
        else:
            st.warning("Please enter a question or request.")

    st.markdown("---")
    # --- Optional: Direct Context API Queries in Sidebar ---
    st.sidebar.title("Direct Context Queries")
    st.sidebar.markdown("Test individual context APIs (requires backend to be running).")

    sidebar_location = st.sidebar.text_input("Location for Weather API:", placeholder="e.g., Delhi", key="sidebar_loc_weather")

    if st.sidebar.button("Weather Update"):
        if sidebar_location:
            weather_endpoint = f"{BACKEND_API_URL}/context/weather"
            payload = {"city": sidebar_location}
            try:
                with st.spinner("Fetching weather..."):
                    response = requests.post(weather_endpoint, headers=headers, json=payload, timeout=20)
                if response.status_code == 200:
                    st.sidebar.subheader(f"Weather for {sidebar_location}")
                    st.sidebar.json(response.json())
                else:
                    st.sidebar.error(f"Weather API Error {response.status_code}: {response.json().get('detail', response.text)}")
            except requests.exceptions.ConnectionError:
                st.sidebar.error(f"Connection Error: Could not reach backend at {BACKEND_API_URL} for weather. Is it running?")
            except Exception as e:
                st.sidebar.error(f"Failed to fetch weather: {e}")
        else:
            st.sidebar.warning("Please enter a location for weather.")

    if st.sidebar.button("Recent Earthquakes (India Default)"):
        # This button uses default coordinates defined in the backend for the /context/earthquakes endpoint
        eq_endpoint = f"{BACKEND_API_URL}/context/earthquakes"
        # The payload for the default query can be empty if defaults are handled by Pydantic in backend
        # Or send specific defaults if you want to override backend defaults from here
        eq_payload = { 
            "latitude": DEFAULT_LAT, # Using frontend defined default
            "longitude": DEFAULT_LON,
            "radius_km": 1500, 
            "days": 7, 
            "min_magnitude": 4.0 
        } 
        try:
            with st.spinner("Fetching earthquakes..."):
                response = requests.post(eq_endpoint, headers=headers, json=eq_payload, timeout=20)
            if response.status_code == 200:
                st.sidebar.subheader(f"Earthquakes (Near Default/India)")
                st.sidebar.json(response.json())
            else:
                st.sidebar.error(f"Earthquake API Error {response.status_code}: {response.json().get('detail', response.text)}")
        except requests.exceptions.ConnectionError:
            st.sidebar.error(f"Connection Error: Could not reach backend at {BACKEND_API_URL} for earthquakes. Is it running?")
        except Exception as e:
            st.sidebar.error(f"Failed to fetch earthquakes: {e}")
            
    # Add similar buttons for EONET events, News etc. if desired for testing
    if st.sidebar.button("Recent News (India Disaster)"):
        news_endpoint = f"{BACKEND_API_URL}/context/news"
        news_payload = {"search_query": "India disaster OR flood OR cyclone OR earthquake", "page_size": 3}
        try:
            with st.spinner("Fetching news..."):
                response = requests.post(news_endpoint, headers=headers, json=news_payload, timeout=20)
            if response.status_code == 200:
                st.sidebar.subheader("Recent Disaster News")
                st.sidebar.json(response.json())
            else:
                st.sidebar.error(f"News API Error {response.status_code}: {response.json().get('detail', response.text)}")
        except requests.exceptions.ConnectionError:
            st.sidebar.error(f"Connection Error: Could not reach backend at {BACKEND_API_URL} for news. Is it running?")
        except Exception as e:
            st.sidebar.error(f"Failed to fetch news: {e}")

    # END OF LINE
import requests

try:
    response = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", timeout=10)
    print(response.json())
except requests.exceptions.Timeout:
    print("⏰ API timed out")
except requests.exceptions.RequestException as e:
    print(f"❌ Failed to fetch data: {e}")