FROM python:3.11-slim

# Install ffmpeg for capturing screenshots from video streams
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set up the working directory
WORKDIR /app

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application script
COPY app.py .

# Run the script
CMD ["python", "-u", "app.py"]
