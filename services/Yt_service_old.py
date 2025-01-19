import os
import re
import logging
import requests
import urllib.error
from typing import List, Dict
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
import google.generativeai as genai
import whisper
from config import VIDEO_ID_PATTERN, CONVERSATION_HISTORY_LIMIT, SUMMARY_WORD_LIMIT, MAX_TRANSCRIPT_LENGTH

# Initialize Whisper model for speech-to-text
whisper_model = whisper.load_model("base")

# Temporary variable to store YouTube transcripts instead of Redis
transcript_cache = {}

# Initialize Google Gemini model
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def extract_video_id(youtube_video_url):
    match = re.search(VIDEO_ID_PATTERN, youtube_video_url)
    if match:
        video_id = match.group(1)
        logging.info(f"Extracted video ID: {video_id}")
        return video_id
    logging.error("Failed to extract video ID from URL.")
    raise ValueError("Invalid YouTube URL format. Please ensure the URL is valid.")

def download_audio(video_id):
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
            raise RuntimeError("Failed to download audio from YouTube. The video may not be in English or is restricted.")
        else:
            logging.error(f"Error downloading audio for video ID {video_id}: {e}")
            raise RuntimeError("Failed to download audio from YouTube.")
    except Exception as e:
        logging.error(f"Error downloading audio for video ID {video_id}: {e}")
        raise RuntimeError("Failed to download audio from YouTube.")

def transcribe_audio(audio_file_path):
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
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            logging.info(f"Deleted the audio file: {audio_file_path}")

def fetch_transcript(video_id):
    cookies_file = 'youtube_cookies.txt'  # Make sure this file is accessible
    
    try:
        # Fetch transcript using cookies
        transcript = YouTubeTranscriptApi.get_transcript(video_id, cookies=cookies_file)
        
        # Create an empty list to store all the transcript texts
        transcript_paragraph = []

        # Loop through each entry in the transcript
        for entry in transcript:
            text = entry['text']
            transcript_paragraph.append(text)

        # Join the list into a single string (paragraph)
        transcript_paragraph = ' '.join(transcript_paragraph)
        
        logging.info(f"Fetched transcript for video ID {video_id}.")
        return transcript_paragraph
    
    except (NoTranscriptFound, TranscriptsDisabled):
        logging.warning(f"No transcript available for video ID {video_id}.")
        return None
    except Exception as e:
        logging.error(f"Error fetching transcript: {e}")
        raise RuntimeError("Failed to fetch transcript.")


def fetch_video_metadata(video_id):
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

def get_transcript_text(video_id):
    global transcript_cache
    
    if video_id in transcript_cache:
        logging.info("Transcript fetched from temporary cache.")
        return transcript_cache[video_id]
    else:
        transcript_text = fetch_transcript(video_id)
        if not transcript_text:
            logging.info("Attempting to transcribe audio as no transcript is available.")
            audio_file_path = download_audio(video_id)
            transcript_text = transcribe_audio(audio_file_path)
        
        # Store the transcript in the temporary cache
        transcript_cache[video_id] = transcript_text
        return transcript_text

def generate_summary(transcript_text, metadata):
    try:
        model = genai.GenerativeModel("gemini-pro")
        title = metadata.get("title", "")
        description = metadata.get("author_name", "")

        # Truncate transcript if necessary
        if len(transcript_text) > MAX_TRANSCRIPT_LENGTH:
            transcript_text = transcript_text[:MAX_TRANSCRIPT_LENGTH]

        # Increase the desired word count for the summary
        detailed_summary_word_limit = SUMMARY_WORD_LIMIT * 2  # Adjust as needed for larger summaries

        prompt = (
            f"You are an expert summarizer. Read the following transcript and generate a highly detailed, "
            f"in-depth summary covering all key points and important information. The summary should be approximately "
            f"{detailed_summary_word_limit} words.\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            f"Transcript:\n{transcript_text}\n\n"
            f"Detailed Summary:"
        )
        response = model.generate_content(prompt)
        summary = response.text.strip()
        return summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        raise RuntimeError("Failed to generate summary.")

def merge_summaries(*summaries):
    try:
        model = genai.GenerativeModel("gemini-pro")
        
        # Prepare the prompt with all summaries to merge
        combined_summaries_text = "\n\n".join([f"Summary {i+1}:\n{summary}" for i, summary in enumerate(summaries)])

        prompt = (
            f"You are an expert in summarization. You are provided with multiple summaries from different sources. "
            f"Your task is to intelligently merge all the summaries into a single, cohesive, and highly detailed summary. "
            f"The merged summary should cover all key points from all sources, and it should be clear and concise.\n\n"
            f"{combined_summaries_text}\n\n"
            f"Final Merged Summary:"
        )

        response = model.generate_content(prompt)
        combined_summary = response.text.strip()
        return combined_summary
    except Exception as e:
        logging.error(f"Error merging summaries: {e}")
        raise RuntimeError("Failed to merge summaries.")

def answer_question(transcript_text, metadata, user_question, conversation_history):
    try:
        model = genai.GenerativeModel("gemini-pro")
        title = metadata.get("title", "Unknown Title")
        description = metadata.get("author_name", "Unknown Author")

        # Prepare conversation context
        conversation_context = ""
        if conversation_history:
            conversation_context = "\n".join(
                [f"User: {entry['question']}\nAssistant: {entry['answer']}" for entry in conversation_history[-CONVERSATION_HISTORY_LIMIT:]]
            )

        # Truncate transcript if necessary
        if len(transcript_text) > MAX_TRANSCRIPT_LENGTH:
            transcript_text = transcript_text[:MAX_TRANSCRIPT_LENGTH]

        # Adjust the prompt based on available data (transcript and conversation history)
        prompt = (
            f"You are an intelligent assistant. Based on the transcript and previous conversation, answer the user's question.\n\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            f"Transcript:\n{transcript_text}\n\n"
            f"Conversation History:\n{conversation_context}\n\n"
            f"User Question:\n{user_question}\n\n"
            f"Answer in as much detail as possible:"
        )

        response = model.generate_content(prompt)
        logging.info(f"Full API Response: {response}")

        # Extract answer if available
        if response.candidates and hasattr(response.candidates[0], 'content'):
            content = response.candidates[0].content
            if content.parts and hasattr(content.parts[0], 'text'):
                answer = content.parts[0].text.strip()
                if not answer:
                    # Retry with a fallback prompt if the answer is not meaningful
                    logging.info("No meaningful answer found, retrying with a fallback prompt.")
                    fallback_prompt = (
                        f"Try again. Based on the following content, answer the user's question.\n\n"
                        f"Document Content:\n{transcript_text}\n\n"
                        f"User Question:\n{user_question}\n\n"
                        f"Answer in as much detail as possible:"
                    )
                    response = model.generate_content(fallback_prompt)
                    answer = response.candidates[0].content.parts[0].text.strip()
                return answer
            else:
                logging.error("No 'text' found in content parts. Likely failure to generate an appropriate answer.")
                raise RuntimeError("Failed to generate answer due to missing content.")
        else:
            logging.error("No candidates or content found in the model's response.")
            raise RuntimeError("Failed to generate answer. No valid content in the response.")

    except Exception as e:
        logging.error(f"Error generating answer: {e}")
        raise RuntimeError("Failed to generate answer.")

def merge_answers(*answers, question):
    try:
        model = genai.GenerativeModel("gemini-pro")
        
        # Filter out empty answers
        valid_answers = [answer for answer in answers if answer]
        if not valid_answers:
            logging.info("No valid answers to merge.")
            return "No valid information available to answer the question."

        # Combine all valid answers
        combined_answers_text = "\n\n".join([f"Answer {i+1}:\n{answer}" for i, answer in enumerate(valid_answers)])

        prompt = (
            f"You are an intelligent assistant tasked with answering a question based on multiple sources of information.\n\n"
            f"Question: {question}\n\n"
            f"Below are answers from various sources:\n\n"
            f"{combined_answers_text}\n\n"
            f"Your task is to:\n"
            f"1. Identify the key points from all sources of information.\n"
            f"2. Combine these key points to provide a comprehensive, unified response.\n"
            f"3. Ensure the final answer is detailed, well-structured, and addresses all parts of the question.\n"
            f"4. Present the information as a cohesive answer without mentioning specific sources.\n"
            f"5. If there are any discrepancies between the sources, reconcile them in your response.\n\n"
            f"Provide a clear, direct, and coherent response that intelligently merges all available information."
        )

        # Attempt to generate the answer using the model
        response = model.generate_content(prompt)

        # Check if the response is valid
        if response.candidates and hasattr(response.candidates[0], 'content'):
            content = response.candidates[0].content
            if content.parts and hasattr(content.parts[0], 'text'):
                combined_answer = content.parts[0].text.strip()

                # Retry if the answer seems too short or insufficient
                if len(combined_answer) < 100:
                    logging.info("Short answer generated. Retrying with a fallback prompt.")
                    fallback_prompt = (
                        f"Try again. Based on the following answers from multiple sources, generate a more detailed answer.\n\n"
                        f"{combined_answers_text}\n\n"
                        f"Answer:"
                    )
                    response = model.generate_content(fallback_prompt)
                    combined_answer = response.candidates[0].content.parts[0].text.strip()

                return combined_answer
            else:
                logging.error("No 'text' found in content parts.")
                raise RuntimeError("Failed to merge answers due to missing content.")
        else:
            logging.error("No valid candidates or content found in the response.")
            raise RuntimeError("Failed to merge answers. No valid content in the model's response.")
    
    except Exception as e:
        logging.error(f"Error merging answers: {e}")
        raise RuntimeError("Failed to merge answers.")

# Function to clear the transcript cache after a conversation ends
def end_conversation():
    global transcript_cache
    transcript_cache.clear()
    logging.info("All transcripts cleared from temporary cache.")

def prepare_summary_content(summary, metadata):
    """
    Prepare the content for saving the summary report.

    Args:
        summary (str): The summary text.
        metadata (dict): Metadata about the summary (title, author).

    Returns:
        str: Formatted summary content ready for saving to file.
    """
    content = f"Title: {metadata.get('title', 'Unknown Title')}\n"
    content += f"Author: {metadata.get('author_name', 'Unknown Author')}\n\n"
    content += "Summary:\n\n"
    content += summary
    return content