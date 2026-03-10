FROM python:3.11-slim

# Install ffmpeg for capturing screenshots from video streams
# curl is added for healthchecks
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

# Set up the working directory
WORKDIR /app

# Copy dependencies first for better caching
COPY watcher-app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
# This includes watcher-app/ and tests/
COPY . .

# Set PYTHONPATH to include the watcher-app directory so imports work
ENV PYTHONPATH=/app/watcher-app

# Run the script from the root context
CMD ["python", "-u", "watcher-app/app.py"]
