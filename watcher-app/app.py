import os
import time
import base64
import requests
import subprocess
import json
import shutil
import logging
import uuid
import re
from datetime import datetime
from websocket import create_connection, WebSocketException

# --- Configuration ---
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

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

os.makedirs(Config.FAILURES_DIR, exist_ok=True)

PROMPT = (
    "Analyze this image of a 3D print in progress. "
    "Is the print failing? Look for spaghetti (tangled mess of filament), "
    "a detached object, or a large blob of filament on the nozzle. "
    "Respond with a confidence score from 0 to 100, where 100 is certain failure and 0 is perfectly fine. "
    "Answer only with the number."
)

def sdcp_request(payload=None, timeout=10):
    """Sends a request to the SDCP API using WebSocket and returns the response."""
    ws_url = f"ws://{Config.PRINTER_IP}:3030/websocket"
    ws = None
    try:
        ws = create_connection(ws_url, timeout=timeout)
        
        if payload:
            ws.send(json.dumps(payload))
        
        # SDCP often broadcasts status, so we might need to wait for a valid JSON response
        for _ in range(5):
            try:
                result = ws.recv()
                if not result:
                    continue
                
                # Try to extract JSON from the response
                start = result.find('{')
                end = result.rfind('}')
                if start != -1 and end != -1:
                    return json.loads(result[start:end+1])
            except (json.JSONDecodeError, WebSocketException):
                continue
            time.sleep(0.2)
            
        return None
    except Exception as e:
        logger.debug(f"SDCP connection error: {e}")
        return None
    finally:
        if ws:
            ws.close()

def is_printer_printing():
    """Check if the printer is currently active and printing via SDCP."""
    for _ in range(3):
        status = sdcp_request(None, timeout=5)
        if status and "Status" in status:
            s_obj = status["Status"]
            print_status = s_obj.get("CurrentStatus", [0])
            
            # SDCP v3: 1 in CurrentStatus list often indicates active/paused state
            is_active = (1 in print_status) if isinstance(print_status, list) else (print_status == 1)
                
            if is_active:
                p_info_status = s_obj.get("PrintInfo", {}).get("Status")
                # 13 is the SDCP status code for 'Printing'
                return p_info_status == 13
            
            return False
        time.sleep(1)
    return False

def pause_printer():
    """Send SDCP pause command to the printer."""
    logger.warning("CRITICAL: Failure threshold reached. Pausing the printer!")
    
    request_id = str(uuid.uuid4())
    payload = {
        "Id": uuid.uuid4().hex,
        "Data": {
            "Cmd": 1,
            "Data": {
                "Type": 1 # 1 is Pause in SDCP V3
            },
            "RequestID": request_id,
            "MainboardID": Config.MAINBOARD_ID,
            "TimeStamp": int(time.time() * 1000)
        },
        "Topic": f"sdcp/request/{Config.MAINBOARD_ID}"
    }
    
    resp = sdcp_request(payload)
    if resp:
        logger.info(f"Pause command sent. Response: {resp.get('Attributes', {}).get('Result', 'Sent')}")
    else:
        logger.error("Failed to confirm pause command receipt.")

def capture_screenshot(output_path="current_frame.jpg"):
    """Capture a single frame from the printer's video stream using ffmpeg."""
    command = [
        'ffmpeg',
        '-i', Config.PRINTER_VIDEO_URL,
        '-ss', '0.5',
        '-frames:v', '1',
        '-q:v', '2',
        output_path,
        '-y'
    ]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(output_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg failed to capture screenshot: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during screenshot capture: {e}")
        return False

def ensure_model_pulled():
    """Verify if the requested AI model is available in Ollama, pull if missing."""
    try:
        resp = requests.get(f"{Config.OLLAMA_URL}/api/tags", timeout=10)
        resp.raise_for_status()
        
        models = [m['name'] for m in resp.json().get('models', [])]
        if any(Config.MODEL_NAME in m for m in models):
            logger.info(f"Model '{Config.MODEL_NAME}' is ready.")
            return True
        
        logger.info(f"Model '{Config.MODEL_NAME}' not found. Pulling... (this may take a few minutes)")
        with requests.post(f"{Config.OLLAMA_URL}/api/pull", json={"name": Config.MODEL_NAME}, stream=True, timeout=900) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    # Keep-alive/Progress could be logged here if needed
                    pass
        logger.info(f"Model '{Config.MODEL_NAME}' successfully pulled.")
        return True
    except Exception as e:
        logger.error(f"Error checking or pulling model: {e}")
        return False

def analyze_image_with_ollama(image_path):
    """Send the captured image to Ollama for failure detection analysis."""
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        payload = {
            "model": Config.MODEL_NAME,
            "prompt": PROMPT,
            "stream": False,
            "images": [encoded_string]
        }
        
        resp = requests.post(f"{Config.OLLAMA_URL}/api/generate", json=payload, timeout=90)
        resp.raise_for_status()
        
        response_text = resp.json().get("response", "").strip()
        if not response_text:
            logger.warning("Ollama returned an empty response.")
            return False

        # Extract the first numeric sequence from the AI's response
        score_match = re.search(r'\d+', response_text)
        if score_match:
            confidence = int(score_match.group())
            logger.info(f"AI failure confidence: {confidence}% (Threshold: {Config.CONFIDENCE_THRESHOLD}%)")
            return confidence >= Config.CONFIDENCE_THRESHOLD
        
        logger.warning(f"No numeric confidence found in AI response: {response_text}")
        return False
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error communicating with Ollama: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during image analysis: {e}")
        return False

def main_loop():
    """Main execution loop for the print watcher."""
    logger.info(f"Initializing Print Watcher for {Config.PRINTER_IP}...")
    
    # Wait for Ollama service to become reachable
    ollama_ready = False
    for i in range(20):
        try:
            requests.get(f"{Config.OLLAMA_URL}/api/tags", timeout=2)
            ollama_ready = True
            break
        except Exception:
            if i % 5 == 0:
                logger.info("Waiting for Ollama service to start...")
            time.sleep(3)
            
    if not ollama_ready:
        logger.error("Ollama service not reachable after timeout. Exiting.")
        return

    if not ensure_model_pulled():
        logger.error("Could not verify or pull the required AI model. Exiting.")
        return
    
    consecutive_failures = 0
    logger.info("Watcher started. Monitoring printer status...")
    
    while True:
        try:
            if is_printer_printing():
                logger.info("Printer is active. Capturing frame for analysis...")
                
                screenshot_path = "current_frame.jpg"
                if capture_screenshot(screenshot_path):
                    is_failing = analyze_image_with_ollama(screenshot_path)
                    
                    if is_failing:
                        consecutive_failures += 1
                        logger.warning(f"Potential failure detected! ({consecutive_failures}/{Config.FAILURE_THRESHOLD})")
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        failure_save_path = os.path.join(Config.FAILURES_DIR, f"fail_{timestamp}.jpg")
                        shutil.move(screenshot_path, failure_save_path)
                        
                        if consecutive_failures >= Config.FAILURE_THRESHOLD:
                            pause_printer()
                            consecutive_failures = 0
                    else:
                        if consecutive_failures > 0:
                            logger.info("False alarm or clear frame. Resetting failure counter.")
                        consecutive_failures = 0
                else:
                    logger.error("Failed to capture frame from stream.")
            else:
                # Reset counter if printer stops or is paused manually
                consecutive_failures = 0
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
        time.sleep(Config.CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Watcher stopped by user.")
