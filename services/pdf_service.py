import PyPDF2
import docx
import csv
import pandas as pd
from bs4 import BeautifulSoup
import logging
import google.generativeai as genai
from config import SUMMARY_WORD_LIMIT

# Process PDF Files
def process_pdf_file(pdf_file_path):
    """
    Processes the given PDF file and extracts the text.
    """
    try:
        with open(pdf_file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                text += page.extract_text()
            logging.info(f"Successfully extracted text from {pdf_file_path}")
            return text
    except Exception as e:
        logging.error(f"Error processing PDF file {pdf_file_path}: {e}")
        raise RuntimeError(f"Failed to process PDF file: {e}")

# Process DOC/DOCX Files
def process_doc_file(doc_file_path):
    """
    Processes the given DOC or DOCX file and extracts the text.
    """
    try:
        doc = docx.Document(doc_file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        logging.info(f"Successfully extracted text from {doc_file_path}")
        return text
    except Exception as e:
        logging.error(f"Error processing DOC/DOCX file {doc_file_path}: {e}")
        raise RuntimeError(f"Failed to process DOC/DOCX file: {e}")

# Process TXT Files
def process_txt_file(txt_file_path):
    """
    Processes the given TXT file and extracts the text.
    """
    try:
        with open(txt_file_path, 'r', encoding='utf-8') as file:
            text = file.read()
        logging.info(f"Successfully extracted text from {txt_file_path}")
        return text
    except Exception as e:
        logging.error(f"Error processing TXT file {txt_file_path}: {e}")
        raise RuntimeError(f"Failed to process TXT file: {e}")

# Process CSV Files
def process_csv_file(csv_file_path):
    """
    Processes the given CSV file and extracts the text as a comma-separated string.
    """
    try:
        with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            text = "\n".join([", ".join(row) for row in reader])
        logging.info(f"Successfully extracted text from {csv_file_path}")
        return text
    except Exception as e:
        logging.error(f"Error processing CSV file {csv_file_path}: {e}")
        raise RuntimeError(f"Failed to process CSV file: {e}")

# Process XLS/XLSX Files
def process_xls_xlsx_file(xls_xlsx_file_path):
    """
    Processes the given XLS/XLSX file and extracts the data as a string.
    """
    try:
        df = pd.read_excel(xls_xlsx_file_path)
        text = df.to_string()
        logging.info(f"Successfully extracted text from {xls_xlsx_file_path}")
        return text
    except Exception as e:
        logging.error(f"Error processing XLS/XLSX file {xls_xlsx_file_path}: {e}")
        raise RuntimeError(f"Failed to process XLS/XLSX file: {e}")

# Process HTML Files
def process_html_file(html_file_path):
    """
    Processes the given HTML file and extracts the text.
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'html.parser')
            text = soup.get_text()
        logging.info(f"Successfully extracted text from {html_file_path}")
        return text
    except Exception as e:
        logging.error(f"Error processing HTML file {html_file_path}: {e}")
        raise RuntimeError(f"Failed to process HTML file: {e}")

# Summarize Content (using Gemini as an example)
def summarize_content(content):
    """
    Summarizes the provided content using Google Gemini API.
    """
    try:
        model = genai.GenerativeModel("gemini-pro")
        prompt = (
            f"Summarize the following content in approximately {SUMMARY_WORD_LIMIT} words:\n\n"
            f"{content[:10000]}"  # Limit input if needed
        )
        response = model.generate_content(prompt)
        summary = response.text.strip()
        return summary
    except Exception as e:
        logging.error(f"Error summarizing content: {e}")
        raise RuntimeError("Failed to generate content summary.")

# Dispatch function to handle different file types
def process_file(file_path, file_extension):
    """
    Processes the given file based on its extension and extracts the text.
    """
    if file_extension == 'pdf':
        return process_pdf_file(file_path)
    elif file_extension in ['doc', 'docx']:
        return process_doc_file(file_path)
    elif file_extension == 'txt':
        return process_txt_file(file_path)
    elif file_extension == 'csv':
        return process_csv_file(file_path)
    elif file_extension in ['xls', 'xlsx']:
        return process_xls_xlsx_file(file_path)
    elif file_extension == 'html':
        return process_html_file(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
