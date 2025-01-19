import os
import re
import logging
import requests
import urllib.error
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
import whisper
from config import (
    VIDEO_ID_PATTERN,
    CONVERSATION_HISTORY_LIMIT,
    SUMMARY_WORD_LIMIT,
    MAX_TRANSCRIPT_LENGTH
)
from bs4 import BeautifulSoup
import wikipedia
import wikipedia.exceptions
from services.pdf_service import process_file

# Initialize Whisper model for speech-to-text
whisper_model = whisper.load_model("base")

# Initialize Google Gemini model (already configured in config.py)
genai.configure()

##############################################################################
# In-memory structure for storing user data (no database).
# user_data_cache will hold data for all users in a single dictionary:
# {
#     "username1": {
#         "transcripts": { "video_id": "transcript text", ... },
#         "file_contents": { "filename": "file text", ... },
#         "website_contents": { "url": "website text", ... },
#         "wikipedia_contents": { "title": "wiki content", ... },
#         "conversation_history": [ { "question": "...", "answer": "..." }, ... ]
#     },
#     "username2": { ... }
# }
##############################################################################
user_data_cache = {}


def get_or_create_user_data(username: str) -> dict:
    """
    Retrieves the user data cache for the given username.
    If it doesn't exist, create an empty structure.
    """
    if username not in user_data_cache:
        user_data_cache[username] = {
            "transcripts": {},
            "file_contents": {},
            "website_contents": {},
            "wikipedia_contents": {},
            "conversation_history": []
        }
    return user_data_cache[username]


def extract_video_id(youtube_video_url):
    match = re.search(VIDEO_ID_PATTERN, youtube_video_url)
    if match:
        video_id = match.group(1)
        logging.info(f"Extracted video ID: {video_id}")
        return video_id
    logging.error("Failed to extract video ID from URL.")
    raise ValueError("Invalid YouTube URL format. Please ensure the URL is valid.")


def download_audio(video_id):
    """
    Downloads YouTube video audio by video_id using pytube.
    """
    try:
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(youtube_url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            raise RuntimeError("No audio stream found for the video.")
        audio_file_path = audio_stream.download(filename=f"{video_id}.mp4")
        logging.info(f"Downloaded audio for video ID {video_id}.")
        return audio_file_path
    except urllib.error.HTTPError as e:
        if e.code == 400:
            logging.error(f"Bad Request error: {e}")
            raise RuntimeError("Failed to download audio from YouTube. Possibly restricted.")
        else:
            logging.error(f"Error downloading audio for video ID {video_id}: {e}")
            raise RuntimeError("Failed to download audio from YouTube.")
    except Exception as e:
        logging.error(f"Error downloading audio for video ID {video_id}: {e}")
        raise RuntimeError("Failed to download audio from YouTube.")


def transcribe_audio(audio_file_path, delete_after=True):
    """
    Transcribes audio using Whisper.
    """
    try:
        logging.info("Transcribing audio with Whisper model...")
        result = whisper_model.transcribe(audio_file_path)
        transcript = result['text']
        logging.info("Audio transcription successful.")
        return transcript
    except Exception as e:
        logging.error(f"Error transcribing audio: {e}")
        raise RuntimeError("Audio transcription failed.")
    finally:
        if delete_after and os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            logging.info(f"Deleted the audio file: {audio_file_path}")


def fetch_transcript_from_external_service(video_id):
    """
    Optionally fetch transcript from an external service.
    If not available, fallback to local download & whisper transcription.
    """
    # Example external transcript URL (change to your real external endpoint if desired)
    transcript_url = "http://13.61.100.173:5000/get_transcript"

    try:
        logging.info(f"Attempting to fetch transcript for video ID: {video_id} from external service.")
        response = requests.post(transcript_url, json={"video_url": f"https://www.youtube.com/watch?v={video_id}"})
        response.raise_for_status()
        data = response.json()

        transcript_paragraph = data.get("transcript")
        if transcript_paragraph:
            logging.info(f"Successfully fetched transcript for {video_id}.")
            return transcript_paragraph
        else:
            logging.warning(f"No transcript available from external service for video ID {video_id}.")
            return None
    except requests.RequestException as e:
        logging.error(f"Error fetching transcript for video ID {video_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error while fetching transcript for video ID {video_id}: {e}")
        return None


def fetch_video_metadata(video_id):
    """
    Fetches YouTube video metadata using oEmbed.
    """
    try:
        metadata_url = f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(metadata_url)
        response.raise_for_status()
        metadata = response.json()
        logging.info(f"Fetched metadata for video ID {video_id}.")
        return metadata
    except requests.RequestException as e:
        logging.error(f"Error fetching metadata: {e}")
        raise RuntimeError("Failed to fetch video metadata.")


def get_transcript_text(username, video_id):
    """
    Retrieves or generates the transcript text for a given YouTube video.
    Uses in-memory cache to avoid re-fetching or re-transcribing.
    """
    user_data = get_or_create_user_data(username)

    # Check if we already have the transcript in memory
    if video_id in user_data["transcripts"]:
        logging.info("Transcript fetched from user's temporary cache.")
        return user_data["transcripts"][video_id]

    # Try fetching from an external transcript service
    transcript_text = fetch_transcript_from_external_service(video_id)
    if transcript_text:
        # Cache it
        user_data["transcripts"][video_id] = transcript_text
        return transcript_text

    # If external transcript is not available, do local download + whisper
    logging.info("Attempting to transcribe audio as no transcript is available from external service.")
    audio_file_path = download_audio(video_id)
    transcript_text = transcribe_audio(audio_file_path)

    user_data["transcripts"][video_id] = transcript_text
    return transcript_text


def get_file_content(username, file_name, file_extension, file_path):
    """
    Process file if not processed before and store in memory.
    """
    user_data = get_or_create_user_data(username)

    if file_name in user_data["file_contents"]:
        logging.info(f"File content fetched from user's cache: {file_name}")
        return user_data["file_contents"][file_name]
    else:
        # If it's an audio/video extension, transcribe with Whisper
        if file_extension.lower() in ['mp3', 'mp4', 'wav', 'avi', 'mkv', 'flv', 'mov']:
            logging.info(f"Processing audio/video file {file_name} for transcription.")
            transcript_text = transcribe_audio(file_path, delete_after=False)
            user_data["file_contents"][file_name] = transcript_text
            return transcript_text
        else:
            # Otherwise, use PDF service's process_file
            content_text = process_file(file_path, file_extension)
            user_data["file_contents"][file_name] = content_text
            return content_text


def get_website_content(username, website_url):
    """
    Fetches website text content (cached in memory).
    """
    user_data = get_or_create_user_data(username)

    if website_url in user_data["website_contents"]:
        logging.info(f"Website content from user's cache: {website_url}")
        return user_data["website_contents"][website_url]
    else:
        try:
            response = requests.get(website_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ', strip=True)
            user_data["website_contents"][website_url] = text
            return text
        except Exception as e:
            logging.error(f"Error fetching website content from {website_url}: {e}")
            raise RuntimeError(f"Failed to fetch website content from {website_url}")


def get_wikipedia_content(username, wiki_title):
    """
    Fetches Wikipedia page content (cached in memory).
    """
    user_data = get_or_create_user_data(username)

    if wiki_title in user_data["wikipedia_contents"]:
        logging.info(f"Wikipedia content from user's cache: {wiki_title}")
        return user_data["wikipedia_contents"][wiki_title]
    else:
        try:
            page = wikipedia.page(wiki_title)
            content = page.content
            user_data["wikipedia_contents"][wiki_title] = content
            return content
        except wikipedia.exceptions.DisambiguationError as e:
            logging.error(f"Disambiguation error for '{wiki_title}': {e}")
            raise RuntimeError(f"The title '{wiki_title}' is ambiguous. Possible options: {e.options}")
        except wikipedia.exceptions.PageError as e:
            logging.error(f"Page error for '{wiki_title}': {e}")
            raise RuntimeError(f"The page '{wiki_title}' does not exist on Wikipedia.")
        except Exception as e:
            logging.error(f"Error fetching Wikipedia content for '{wiki_title}': {e}")
            raise RuntimeError(f"Failed to fetch Wikipedia content for '{wiki_title}'.")


def generate_summary(content_text, metadata, username):
    """
    Uses Google Gemini to generate a detailed summary of the content.
    """
    try:
        model = genai.GenerativeModel("gemini-pro")
        title = metadata.get("title", "")
        description = metadata.get("author_name", "")

        if len(content_text) > MAX_TRANSCRIPT_LENGTH:
            content_text = content_text[:MAX_TRANSCRIPT_LENGTH]

        detailed_summary_word_limit = SUMMARY_WORD_LIMIT * 2

        prompt = (
            f"You are an expert summarizer. Read the following content and generate a highly detailed summary of "
            f"about {detailed_summary_word_limit} words.\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            f"Content:\n{content_text}\n\n"
            f"Detailed Summary:"
        )

        response = model.generate_content(prompt)
        summary = response.text.strip()
        return summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        raise RuntimeError("Failed to generate summary.")


def merge_summaries(*summaries):
    """
    Merges multiple summaries into one cohesive summary using Google Gemini.
    """
    try:
        model = genai.GenerativeModel("gemini-pro")
        combined_summaries_text = "\n\n".join([f"Summary {i+1}:\n{summary}" for i, summary in enumerate(summaries)])

        prompt = (
            f"You are an expert in summarization. You have multiple summaries. "
            f"Merge them into one cohesive summary covering all key points.\n\n"
            f"{combined_summaries_text}\n\n"
            f"Final Merged Summary:"
        )

        response = model.generate_content(prompt)
        combined_summary = response.text.strip()
        return combined_summary
    except Exception as e:
        logging.error(f"Error merging summaries: {e}")
        raise RuntimeError("Failed to merge summaries.")


def answer_question(content_text, metadata, user_question, conversation_history, username):
    """
    Answers a question based on the content_text, conversation history, etc.
    """
    try:
        model = genai.GenerativeModel("gemini-pro")
        title = metadata.get("title", "Unknown Title")
        description = metadata.get("author_name", "Unknown Author")

        conversation_context = ""
        if conversation_history:
            conversation_context = "\n".join(
                [
                    f"User: {entry['question']}\nAssistant: {entry['answer']}"
                    for entry in conversation_history[-CONVERSATION_HISTORY_LIMIT:]
                ]
            )

        if len(content_text) > MAX_TRANSCRIPT_LENGTH:
            content_text = content_text[:MAX_TRANSCRIPT_LENGTH]

        prompt = (
            f"You are an intelligent assistant. Use the content and conversation history below to answer the user's question.\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            f"Content:\n{content_text}\n\n"
            f"Conversation History:\n{conversation_context}\n\n"
            f"User Question:\n{user_question}\n\n"
            f"Answer in detail:"
        )

        response = model.generate_content(prompt)
        answer = response.text.strip()

        if not answer:
            logging.info("No meaningful answer found, retrying with a fallback prompt.")
            fallback_prompt = (
                f"Try again. Based on the following content, answer the user's question.\n\n"
                f"Content:\n{content_text}\n\n"
                f"User Question:\n{user_question}\n\n"
                f"Answer in as much detail as possible:"
            )
            response = model.generate_content(fallback_prompt)
            answer = response.text.strip()

        return answer
    except Exception as e:
        logging.error(f"Error generating answer: {e}")
        raise RuntimeError("Failed to generate answer.")


def merge_answers(*answers, question):
    """
    Merges multiple answers into a single, consolidated answer.
    """
    try:
        model = genai.GenerativeModel("gemini-pro")
        valid_answers = [a for a in answers if a.strip()]
        if not valid_answers:
            return "No valid information available to answer the question."

        combined_answers_text = "\n\n".join([f"Answer {i+1}:\n{ans}" for i, ans in enumerate(valid_answers)])
        prompt = (
            f"You are an intelligent assistant. You have multiple answers to the same question:\n\n"
            f"Question: {question}\n\n"
            f"{combined_answers_text}\n\n"
            f"Merge them into one cohesive, comprehensive answer that addresses all points without referencing sources."
        )

        response = model.generate_content(prompt)
        combined_answer = response.text.strip()
        if not combined_answer:
            raise RuntimeError("Empty combined answer.")
        return combined_answer
    except Exception as e:
        logging.error(f"Error merging answers: {e}")
        raise RuntimeError("Failed to merge answers.")


def end_conversation(username):
    """
    Clears all data from memory for this specific user.
    """
    if username in user_data_cache:
        del user_data_cache[username]
        logging.info(f"All data cleared from memory for user {username}.")


def prepare_summary_content(summary, metadata):
    """
    Prepares the content for saving the summary report (to a string).
    """
    content = f"Title: {metadata.get('title', 'Unknown Title')}\n"
    content += f"Author: {metadata.get('author_name', 'Unknown Author')}\n\n"
    content += "Summary:\n\n"
    content += summary
    return content
