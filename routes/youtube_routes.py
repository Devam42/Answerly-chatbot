import os
import time
import logging
import threading
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

from utils.error_handling import handle_errors
from services.pdf_service import process_file, summarize_content
from services.youtube_service import (
    get_or_create_user_data,
    extract_video_id,
    fetch_video_metadata,
    get_transcript_text,
    generate_summary,
    answer_question,
    merge_summaries,
    merge_answers,
    prepare_summary_content,
    get_file_content,
    get_website_content,
    get_wikipedia_content,
    end_conversation
)

youtube_bp = Blueprint('youtube_bp', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'txt', 'csv', 'xls', 'xlsx', 'html',
    'mp3', 'mp4', 'wav', 'avi', 'mkv', 'flv', 'mov'
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

##############################################################################
# In-memory only. No database. We'll store everything in user_data_cache
# accessed via get_or_create_user_data(username).
##############################################################################

# /api/summary
@youtube_bp.route('/api/summary', methods=['POST'])
@handle_errors
def generate_summary_endpoint():
    data = request.form
    username = data.get('username')

    # Up to 5 YouTube links, websites, Wikipedia titles, or files
    youtube_links = [data.get(f'youtube_link{i}') for i in range(1, 6) if data.get(f'youtube_link{i}')]
    website_urls = [data.get(f'website_url{i}') for i in range(1, 6) if data.get(f'website_url{i}')]
    wikipedia_titles = [data.get(f'wikipedia_title{i}') for i in range(1, 6) if data.get(f'wikipedia_title{i}')]
    uploaded_files = [request.files.get(f'uploaded_file{i}') for i in range(1, 6) if request.files.get(f'uploaded_file{i}')]

    if not username:
        return jsonify({"error": "Username is required."}), 400
    if not youtube_links and not uploaded_files and not website_urls and not wikipedia_titles:
        return jsonify({"error": "No links, files, or titles provided."}), 400

    get_or_create_user_data(username)  # ensure we have a user structure
    unsupported_youtube_links, unsupported_files = [], []
    unsupported_websites, unsupported_wikipedia_titles = [], []

    youtube_summaries = []
    for link in youtube_links:
        try:
            video_id = extract_video_id(link)
            metadata = fetch_video_metadata(video_id)
            content_text = get_transcript_text(username, video_id)
            youtube_summaries.append(generate_summary(content_text, metadata, username))
        except Exception as e:
            logging.error(f"Error processing YouTube link {link}: {e}")
            unsupported_youtube_links.append(link)

    file_summaries = []
    for upfile in uploaded_files:
        try:
            if allowed_file(upfile.filename):
                file_extension = upfile.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(upfile.filename)
                file_path = os.path.join('uploads', filename)
                upfile.save(file_path)

                content_text = get_file_content(username, filename, file_extension, file_path)
                file_summaries.append(generate_summary(content_text, {"title": filename}, username))
            else:
                unsupported_files.append(upfile.filename)
        except Exception as e:
            logging.error(f"Error processing file {upfile.filename}: {e}")
            unsupported_files.append(upfile.filename)

    website_summaries = []
    for url in website_urls:
        try:
            content_text = get_website_content(username, url)
            website_summaries.append(generate_summary(content_text, {"title": url}, username))
        except Exception as e:
            logging.error(f"Error processing website {url}: {e}")
            unsupported_websites.append(url)

    wikipedia_summaries = []
    for wtitle in wikipedia_titles:
        try:
            content_text = get_wikipedia_content(username, wtitle)
            wikipedia_summaries.append(generate_summary(content_text, {"title": wtitle}, username))
        except Exception as e:
            logging.error(f"Error processing Wikipedia title {wtitle}: {e}")
            unsupported_wikipedia_titles.append(wtitle)

    # Combine all summaries
    all_summaries = youtube_summaries + file_summaries + website_summaries + wikipedia_summaries
    if all_summaries:
        combined_summary = merge_summaries(*all_summaries)
    else:
        combined_summary = "No valid content to summarize."

    return jsonify({
        "summary": combined_summary,
        "unsupported_youtube_links": unsupported_youtube_links,
        "unsupported_files": unsupported_files,
        "unsupported_websites": unsupported_websites,
        "unsupported_wikipedia_titles": unsupported_wikipedia_titles
    })


# /api/ask_question
@youtube_bp.route('/api/ask_question', methods=['POST'])
@handle_errors
def ask_question_endpoint():
    data = request.form
    username = data.get('username')
    question = data.get('question')

    youtube_links = [data.get(f'youtube_link{i}') for i in range(1, 6) if data.get(f'youtube_link{i}')]
    website_urls = [data.get(f'website_url{i}') for i in range(1, 6) if data.get(f'website_url{i}')]
    wikipedia_titles = [data.get(f'wikipedia_title{i}') for i in range(1, 6) if data.get(f'wikipedia_title{i}')]
    uploaded_files = [request.files.get(f'uploaded_file{i}') for i in range(1, 6) if request.files.get(f'uploaded_file{i}')]

    if not username or not question:
        return jsonify({"error": "Username and question are required."}), 400
    if not youtube_links and not uploaded_files and not website_urls and not wikipedia_titles:
        return jsonify({"error": "No links, files, or titles provided."}), 400

    user_data = get_or_create_user_data(username)
    youtube_answers, file_answers, website_answers, wikipedia_answers = [], [], [], []
    unsupported_youtube_links, unsupported_files, unsupported_websites, unsupported_wikipedia_titles = [], [], [], []

    # We can handle concurrency, but let's do straightforward processing for clarity
    # conversation_history is user_data["conversation_history"]
    conversation_history = user_data["conversation_history"]

    # Process YouTube
    for link in youtube_links:
        try:
            video_id = extract_video_id(link)
            metadata = fetch_video_metadata(video_id)
            content_text = get_transcript_text(username, video_id)
            ans = answer_question(content_text, metadata, question, conversation_history, username)
            youtube_answers.append(ans)
        except Exception as e:
            logging.error(f"Error processing YouTube link {link}: {e}")
            unsupported_youtube_links.append(f"{link}: {str(e)}")

    # Process Files
    for upfile in uploaded_files:
        try:
            if allowed_file(upfile.filename):
                file_extension = upfile.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(upfile.filename)
                file_path = os.path.join('uploads', filename)
                upfile.save(file_path)

                content_text = get_file_content(username, filename, file_extension, file_path)
                ans = answer_question(content_text, {"title": filename}, question, conversation_history, username)
                file_answers.append(ans)
            else:
                unsupported_files.append(f"{upfile.filename}: Unsupported file type")
        except Exception as e:
            logging.error(f"Error processing file {upfile.filename}: {e}")
            unsupported_files.append(f"{upfile.filename}: {str(e)}")

    # Process Websites
    for url in website_urls:
        try:
            content_text = get_website_content(username, url)
            ans = answer_question(content_text, {"title": url}, question, conversation_history, username)
            website_answers.append(ans)
        except Exception as e:
            logging.error(f"Error processing website {url}: {e}")
            unsupported_websites.append(f"{url}: {str(e)}")

    # Process Wikipedia
    for wtitle in wikipedia_titles:
        try:
            content_text = get_wikipedia_content(username, wtitle)
            ans = answer_question(content_text, {"title": wtitle}, question, conversation_history, username)
            wikipedia_answers.append(ans)
        except Exception as e:
            logging.error(f"Error processing Wikipedia title '{wtitle}': {e}")
            unsupported_wikipedia_titles.append(f"{wtitle}: {str(e)}")

    # Merge answers
    all_answers = youtube_answers + file_answers + website_answers + wikipedia_answers
    final_answer = "No valid information available to answer the question."
    if all_answers:
        final_answer = all_answers[0] if len(all_answers) == 1 else merge_answers(*all_answers, question=question)

    # Save Q&A in conversation_history
    conversation_history.append({
        "question": question,
        "answer": final_answer
    })

    return jsonify({
        "answer": final_answer,
        "unsupported_youtube_links": unsupported_youtube_links,
        "unsupported_files": unsupported_files,
        "unsupported_websites": unsupported_websites,
        "unsupported_wikipedia_titles": unsupported_wikipedia_titles
    })


# /api/end_conversation
@youtube_bp.route('/api/end_conversation', methods=['POST'])
@handle_errors
def end_conversation_route():
    data = request.json
    username = data.get('username')
    if not username:
        return jsonify({"error": "Username is required."}), 400

    end_conversation(username)
    return jsonify({"message": f"Conversation ended and in-memory cache cleared for user '{username}'."})