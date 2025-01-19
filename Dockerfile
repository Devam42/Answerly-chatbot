# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies for Whisper, MongoDB, FFmpeg, etc.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev ffmpeg libsm6 libxext6 \
    curl gnupg git && \
    curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add - && \
    echo "deb http://repo.mongodb.org/apt/debian buster/mongodb-org/4.4 main" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends mongodb-org-tools && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements.txt into the container at /app
COPY requirements.txt /app/

# Install Python dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/

# Expose the port the app runs on
EXPOSE 5000

# Run the Flask app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app", "--workers", "3", "--threads", "3"]
