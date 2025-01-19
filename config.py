import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Load Google API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Validate the API Key
if not GOOGLE_API_KEY:
    logging.error("Google API Key is missing! Make sure it's set in the .env file.")
    raise RuntimeError("Google API Key not set. Application cannot run without it.")

# Configure Google Gemini API with the loaded API key
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    logging.info("Google Gemini API successfully configured.")
except Exception as e:
    logging.error(f"Failed to configure Google Gemini API: {e}")
    raise RuntimeError("Error configuring Google Gemini API. Check your API key and configuration.")

# Other constants
VIDEO_ID_PATTERN = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
CONVERSATION_HISTORY_LIMIT = 5
SUMMARY_WORD_LIMIT = 500
MAX_TRANSCRIPT_LENGTH = 10000  # Adjust as per the model's input capacity

# Log the constants to ensure they are loaded properly
logging.info(f"VIDEO_ID_PATTERN: {VIDEO_ID_PATTERN}")
logging.info(f"CONVERSATION_HISTORY_LIMIT: {CONVERSATION_HISTORY_LIMIT}")
logging.info(f"SUMMARY_WORD_LIMIT: {SUMMARY_WORD_LIMIT}")
logging.info(f"MAX_TRANSCRIPT_LENGTH: {MAX_TRANSCRIPT_LENGTH}")
