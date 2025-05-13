    # send_sms_twilio.py
    # Place this file in your PROJECT ROOT directory (e.g., D:\AI Model\)

import os
from dotenv import load_dotenv
import logging
# Attempt to import Twilio client
try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException # For specific Twilio errors
    TWILIO_AVAILABLE = True
except ImportError:
    # This print statement is for when this module is run directly or if logging isn't set up yet
    print("WARNING: Twilio Python library not found. SMS functionality will be disabled. Run 'pip install twilio'")
    TWILIO_AVAILABLE = False
    # Define dummy Client and send_disaster_alert_sms if Twilio is not available
    # so that main.py doesn't crash on import if this file is present but twilio lib is missing.
    class Client: pass 
    def send_disaster_alert_sms(to, body): return False
# Configure logger for this module
# It will inherit FastAPI's logger settings if this module is imported by main.py
# If run standalone, it will use basicConfig.
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Avoid adding multiple handlers if already configured by FastAPI
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Load environment variables from .env file in the project root
# Assumes .env is in the same directory as this script OR in the parent if this script is in a subfolder
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if not os.path.exists(dotenv_path): # If .env not next to this script, try one level up (common for project root)
    project_root_for_env = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root_for_env, '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
    # logger.info(f"Loaded .env from {dotenv_path} for send_sms_twilio.py") # Optional: for debugging .env loading
else:
    logger.warning(f".env file not found at {dotenv_path} or its parent. Twilio credentials might be missing.")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
twilio_client = None
if TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}", exc_info=True)
elif TWILIO_AVAILABLE: # Library is there, but keys are missing
    logger.warning("Twilio credentials (ACCOUNT_SID, AUTH_TOKEN, or PHONE_NUMBER) not fully set in .env. SMS alerts will be disabled.")
# If not TWILIO_AVAILABLE, the warning from import block already covered it.
def send_disaster_alert_sms(to_phone_number: str, message_body: str) -> bool:
    """
    Sends an SMS alert using Twilio.
    Args:
        to_phone_number: The recipient's phone number (e.g., "+916381198548").
                           Must be in E.164 format.
        message_body: The text of the alert message (max 1600 characters,
                      but typically aim for standard SMS length ~160 chars).
    Returns:
        True if the message was successfully queued by Twilio, False otherwise.
    """
    if not TWILIO_AVAILABLE:
        logger.error("Twilio library not installed. Cannot send SMS.")
        return False
    if not twilio_client:
        logger.error("Twilio client not initialized (check credentials). Cannot send SMS.")
        return False
    
    if not to_phone_number or not message_body:
        logger.error("Recipient phone number or message body is missing for SMS.")
        return False
    # Basic validation for phone number format (very simple check)
    if not to_phone_number.startswith('+') or not to_phone_number[1:].isdigit():
        logger.error(f"Invalid recipient phone number format: {to_phone_number}. Must be E.164 (e.g., +916381198548).")
        return False
    
    # Check message length (Twilio handles concatenation, but good to be aware)
    if len(message_body) > 1600: # Twilio's max for a single message API call
        logger.warning(f"SMS message body is very long ({len(message_body)} chars). It will be segmented by Twilio.")
    
    try:
        logger.info(f"Attempting to send SMS to {to_phone_number} from {TWILIO_PHONE_NUMBER}")
        message = twilio_client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone_number
        )
        # Possible statuses: "queued", "failed", "sent", "delivered", "undelivered"
        logger.info(f"SMS to {to_phone_number} - SID: {message.sid}, Status: {message.status}, Error: {message.error_message or 'None'}")
        
        # Consider "queued" or "sent" as success for this function's purpose
        if message.status in ['queued', 'sent']:
            return True
        else:
            logger.error(f"SMS to {to_phone_number} failed with status: {message.status}, Error: {message.error_code} - {message.error_message}")
            return False
    except TwilioRestException as e: # Specific Twilio API errors
        logger.error(f"Twilio API error sending SMS to {to_phone_number}: {e}", exc_info=True)
        return False
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected error sending SMS to {to_phone_number}: {e}", exc_info=True)
        return False
# --- Standalone Test ---
if __name__ == "__main__":
    print("--- Testing send_sms_twilio.py Standalone ---")
    if not TWILIO_AVAILABLE:
        print("Twilio library is not installed. Cannot perform test.")
    elif not twilio_client:
        print("Twilio client not initialized. Check .env for TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER.")
    else:
        # IMPORTANT: Replace with a phone number you have VERIFIED in your Twilio trial account.
        test_recipient_phone = "+91XXXXXXXXXX"  # e.g., your own mobile number
        test_message = "Hello from your AI Disaster Assistant! This is a test SMS via Twilio."
        if "X" in test_recipient_phone:
            print("\n!!! PLEASE EDIT 'test_recipient_phone' IN THE SCRIPT WITH A VERIFIED NUMBER TO TEST SMS SENDING !!!")
        else:
            print(f"\nAttempting to send a test SMS to: {test_recipient_phone}")
            print(f"Using Twilio Number: {TWILIO_PHONE_NUMBER}")
            print(f"Message: {test_message}")
            
            if send_disaster_alert_sms(test_recipient_phone, test_message):
                print("\nTest SMS request sent successfully (or queued). Check your phone and Twilio logs.")
            else:
                print("\nFailed to send test SMS. Check logs above and Twilio console for errors.")
