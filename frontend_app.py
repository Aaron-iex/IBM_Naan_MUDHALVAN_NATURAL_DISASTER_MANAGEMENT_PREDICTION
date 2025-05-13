# frontend_app.py
import streamlit as st
import requests
import os
from dotenv import load_dotenv
import json 
import pandas as pd # For st.map if displaying multiple points

# --- Define default coordinates for frontend use ---
DEFAULT_LAT = 20.5937 
DEFAULT_LON = 78.9629 
INDIA_BBOX_STR = "68,6,98,38" # For EONET API if needed directly by frontend

# --- Load environment variables ---
dotenv_path = os.path.join(os.path.dirname(__file__), '.env') 
if not os.path.exists(dotenv_path):
    project_root_for_env = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root_for_env, '.env')
if os.path.exists(dotenv_path): load_dotenv(dotenv_path=dotenv_path)
else: print(f"Warning: .env file not found. API keys might be missing.")

# --- Configuration ---
BACKEND_API_URL = os.getenv("DEPLOYED_FASTAPI_URL", "http://127.0.0.1:8000") 
FASTAPI_API_KEY = os.getenv("FASTAPI_SECRET_KEY") 

st.set_page_config(
    page_title="AI Disaster Assistant", 
    layout="wide", 
    initial_sidebar_state="expanded",
    page_icon="🌍"
)

st.title("🌍 AI Disaster Management & Context Assistant")
st.caption("Leveraging AI and real-time data for enhanced situational awareness and safety advisories in India.")

if not FASTAPI_API_KEY:
    st.error("CRITICAL ERROR: FASTAPI_SECRET_KEY is not set. Cannot communicate with the backend API.")
else:
    headers = {"X-API-Key": FASTAPI_API_KEY, "Content-Type": "application/json"}

    # --- Tabs for different sections ---
    tab_assistant, tab_dashboard, tab_alerts = st.tabs(["🤖 AI Assistant", "📊 Real-time Dashboard", "🔔 Send Alert (Demo)"])

    with tab_assistant:
        st.header("Ask the AI Assistant")
        st.markdown("Get information on risks, safety, or current conditions. Provide location for specific context.")
        
        with st.form(key="assistant_form"):
            col1, col2 = st.columns([3, 1])
            with col1:
                user_query = st.text_area("Your Question or Request:", height=100, 
                                          placeholder="e.g., What are the risks of heavy rain in Mumbai?\nSafety procedures for earthquake?\nLatest on Cyclone Remal near Kolkata?")
            with col2:
                location_context = st.text_input("Location Context (Optional):", placeholder="e.g., Mumbai, Delhi")
                # Conceptual: Allow user to provide an image URL for analysis
                image_url_input = st.text_input("Satellite Image URL (Optional):", placeholder="Paste direct image URL")

            submit_button = st.form_submit_button(label="🚀 Get Assistance", use_container_width=True, type="primary")

        if submit_button and user_query:
            process_endpoint = f"{BACKEND_API_URL}/process" 
            payload = {
                "text_input": user_query,
                "location_context": location_context if location_context else None,
                "max_new_tokens": 400,
                "image_url_for_analysis": image_url_input if image_url_input else None
            }
            
            st.info(f"Attempting to connect to backend at: {process_endpoint}")
            try:
                with st.spinner("🔍 Gathering context and generating response... Please wait."):
                    response = requests.post(process_endpoint, headers=headers, json=payload, timeout=120) 
                
                if response.status_code == 200:
                    result = response.json()
                    st.markdown("---")
                    st.subheader("💡 Assistant's Response:")
                    st.markdown(result.get("llm_response", "No response text found from the assistant."))

                    if result.get("potential_sms_alert_draft"):
                        st.markdown("---")
                        st.subheader("📢 Potential SMS Alert Draft by AI:")
                        st.text_area("Suggested SMS:", value=result["potential_sms_alert_draft"], height=80, disabled=True)

                    with st.expander("View Context Used by AI & Raw Data", expanded=False):
                        st.write("**Location Provided by User:**", result.get("location_context_provided", "N/A"))
                        st.write("**Context Summary Used for LLM Prompt:**")
                        st.json(result.get("context_used_summary", {}))
                
                elif response.status_code == 401:
                    st.error("🚫 Authorization Error: Invalid or missing API Key for backend access.")
                else: 
                    st.error(f"⚠️ Error communicating with backend API: Status Code {response.status_code}")
                    try: st.error(f"Backend Error Detail: {response.json().get('detail', response.text)}")
                    except Exception: st.error(f"Raw Backend Error: {response.text}")
            # ... (keep other exception handling as before) ...
            except requests.exceptions.Timeout: st.error("⏳ Error: The request to the backend API timed out.")
            except requests.exceptions.ConnectionError as e: st.error(f"🔗 Connection Error: Could not connect to backend at {BACKEND_API_URL}. Is it running? Detail: {e}")
            except Exception as e: st.error(f"💥 An unexpected error occurred in the frontend: {e}")
        elif submit_button and not user_query:
            st.warning("Please enter a question or request.")

    with tab_dashboard:
        st.header("📊 Real-time Information Dashboard")
        st.markdown("Summary of current conditions and events. Data is fetched on demand.")

        if st.button("🔄 Refresh Dashboard Data", key="refresh_dashboard"):
            # Clear cache for specific functions if you implement caching later
            st.experimental_rerun()

        # --- Weather Section ---
        st.subheader("🌦️ Weather Snapshot")
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            weather_city = st.text_input("Enter city for weather:", "Mumbai", key="dash_weather_city")
        if weather_city:
            weather_endpoint = f"{BACKEND_API_URL}/context/weather"
            payload = {"city": weather_city}
            try:
                with st.spinner(f"Fetching weather for {weather_city}..."):
                    response = requests.post(weather_endpoint, headers=headers, json=payload, timeout=15)
                if response.status_code == 200:
                    w_data = response.json()
                    st.metric(label=f"{w_data.get('city')} Temperature", value=f"{w_data.get('temperature_c', 'N/A')} °C", delta=f"Feels like {w_data.get('feels_like_c', 'N/A')} °C")
                    st.write(f"**Conditions:** {w_data.get('description', 'N/A')}")
                    st.write(f"**Humidity:** {w_data.get('humidity_pct', 'N/A')}% | **Wind:** {w_data.get('wind_speed_mps', 'N/A')} m/s")
                else:
                    st.warning(f"Could not fetch weather for {weather_city}: {response.json().get('detail', response.text)}")
            except Exception as e: st.error(f"Error fetching weather: {e}")
        
        st.markdown("---")
        # --- Earthquakes Section ---
        st.subheader("Recent Earthquakes (India Region)")
        eq_endpoint = f"{BACKEND_API_URL}/context/earthquakes"
        eq_payload = {"latitude": DEFAULT_LAT, "longitude": DEFAULT_LON, "radius_km": 2500, "days": 3, "min_magnitude": 4.0}
        try:
            with st.spinner("Fetching earthquake data..."):
                response = requests.post(eq_endpoint, headers=headers, json=eq_payload, timeout=20)
            if response.status_code == 200:
                quakes_data = response.json()
                quakes = quakes_data.get("earthquakes", [])
                if quakes:
                    st.write(f"Found {quakes_data.get('count')} quakes in the last 3 days (Mag 4.0+). Showing top few:")
                    quake_map_data = []
                    for q in quakes:
                        if q.get("latitude") and q.get("longitude"):
                            quake_map_data.append({"lat": q["latitude"], "lon": q["longitude"], "size": q.get("magnitude", 1)*15}) # Scale size for map
                        st.info(f"Mag {q.get('magnitude')} - {q.get('place')} ({q.get('time_utc','')[:16]}Z)")
                    if quake_map_data:
                        df_quakes = pd.DataFrame(quake_map_data)
                        st.map(df_quakes, zoom=3, use_container_width=True)
                else:
                    st.success("No significant recent earthquakes reported in the default region.")
            else:
                st.warning(f"Could not fetch earthquake data: {response.json().get('detail', response.text)}")
        except Exception as e: st.error(f"Error fetching earthquakes: {e}")

        st.markdown("---")
        # --- EONET Events & News ---
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.subheader("🔥 EONET Natural Events (India)")
            event_endpoint = f"{BACKEND_API_URL}/context/natural_events"
            event_payload = {"days": 7, "category": None} # All categories, last 7 days
            try:
                with st.spinner("Fetching EONET events..."):
                    response = requests.post(event_endpoint, headers=headers, json=event_payload, timeout=20)
                if response.status_code == 200:
                    events_data = response.json().get("events", [])
                    if events_data:
                        for ev in events_data[:5]: # Show top 5
                            st.caption(f"**{ev.get('title')}** ({ev.get('category')}) - Updated: {ev.get('last_update_utc','')[:10]}")
                            if ev.get('link'): st.markdown(f"[More Info]({ev.get('link')})", unsafe_allow_html=True)
                    else: st.info("No major EONET events reported for India recently.")
                else: st.warning(f"Could not fetch EONET events: {response.json().get('detail', response.text)}")
            except Exception as e: st.error(f"Error fetching EONET events: {e}")
        with col_e2:
            st.subheader("📰 Latest Disaster News (India)")
            news_endpoint = f"{BACKEND_API_URL}/context/news"
            news_payload = {"search_query": "India disaster OR flood OR cyclone OR earthquake OR heatwave OR landslide", "page_size": 5}
            try:
                with st.spinner("Fetching news..."):
                    response = requests.post(news_endpoint, headers=headers, json=news_payload, timeout=20)
                if response.status_code == 200:
                    news_data = response.json().get("articles", [])
                    if news_data:
                        for article in news_data:
                            st.caption(f"**{article.get('title')}** ({article.get('source')})")
                            if article.get('url'): st.markdown(f"[Read More]({article.get('url')})", unsafe_allow_html=True)
                    else: st.info("No major disaster news found recently.")
                else: st.warning(f"Could not fetch news: {response.json().get('detail', response.text)}")
            except Exception as e: st.error(f"Error fetching news: {e}")
            
   # with tab_alerts:
   #    st.header("🔔 Send Emergency Alert (Demo)")
   #    st.warning("This is a demonstration feature. In a real system, access would be restricted and numbers would come from a subscriber database.")

   #    with st.form("sms_alert_form"):
   #        recipient_phone = st.text_input("Recipient Phone Number (E.164 format):", placeholder="+91XXXXXXXXXX")
   #        alert_message_manual = st.text_area("Alert Message:", height=100, placeholder="Enter critical alert message here...")
   #        send_sms_button = st.form_submit_button("📲 Send SMS Alert", type="primary")

       #if send_sms_button:
       #    if recipient_phone and alert_message_manual:
       #        #if not twilio_client and "send_sms_twilio" in sys.modules: # Check if twilio was configured in backend
       #             st.error("Twilio client not initialized in the backend. Check .env and backend logs.")
       #        else:
       #            sms_payload = {
       #                "phone_number": recipient_phone,
       #                "alert_message": alert_message_manual
       #            }
       #            sms_endpoint = f"{BACKEND_API_URL}/alerts/send_sms"
       #            try:
       #                with st.spinner("Sending SMS..."):
       #                    sms_response = requests.post(sms_endpoint, headers=headers, json=sms_payload, timeout=30)
       #                if sms_response.status_code == 200:
       #                    st.success(f"SMS alert request sent for {recipient_phone}!")
       #                    st.json(sms_response.json())
       #                else:
       #                    st.error(f"Failed to send SMS (Status {sms_response.status_code}): {sms_response.json().get('detail', sms_response.text)}")
       #            except Exception as e_sms_send:
       #                st.error(f"Error sending SMS request: {e_sms_send}")
       #    else:
       #        st.warning("Please provide both a recipient phone number and an alert message.")

# --- Footer ---
st.markdown("---")
st.caption("Disaster Management Assistant - For Educational Purposes")
st.markdown("Developed by [Aaron Nissi/Organization] - 2025")