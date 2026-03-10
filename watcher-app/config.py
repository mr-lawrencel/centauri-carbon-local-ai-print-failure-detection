import os

class Config:
    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
    PRINTER_IP = os.environ.get("PRINTER_IP")
    MAINBOARD_ID = os.environ.get("MAINBOARD_ID")
    
    if not PRINTER_IP or not MAINBOARD_ID:
        raise ValueError("PRINTER_IP and MAINBOARD_ID environment variables must be set.")
        
    PRINTER_VIDEO_URL = os.environ.get("PRINTER_VIDEO_URL", f"http://{PRINTER_IP}:3031/video")
    CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 60))
    FAILURE_THRESHOLD = int(os.environ.get("FAILURE_THRESHOLD", 5))
    CONFIDENCE_THRESHOLD = int(os.environ.get("CONFIDENCE_THRESHOLD", 80))
    MODEL_NAME = os.environ.get("MODEL_NAME", "moondream")
    FAILURES_DIR = "/app/failures"
