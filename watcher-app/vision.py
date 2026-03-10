import base64
import requests
import subprocess
import os
import re
import logging
from config import Config

logger = logging.getLogger(__name__)

PROMPT = (
    "Analyze this image of a 3D print in progress. "
    "Is the print failing? Look for spaghetti (tangled mess of filament), "
    "a detached object, or a large blob of filament on the nozzle. "
    "Respond with a confidence score from 0 to 100, where 100 is certain failure and 0 is perfectly fine. "
    "Answer only with the number."
)

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
                    pass
        logger.info(f"Model '{Config.MODEL_NAME}' successfully pulled.")
        return True
    except Exception as e:
        logger.error(f"Error checking or pulling model: {e}")
        return False

def extract_confidence_score(text):
    """Extract the first numeric sequence from the AI's response."""
    score_match = re.search(r'\d+', text)
    if score_match:
        return int(score_match.group())
    return None

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

        confidence = extract_confidence_score(response_text)
        if confidence is not None:
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
