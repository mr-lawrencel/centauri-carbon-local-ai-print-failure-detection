import os
import time
import base64
import requests
import subprocess
import json
import socket
import shutil
from datetime import datetime

# --- Configuration ---
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
PRINTER_IP = os.environ.get("PRINTER_IP")

if not PRINTER_IP:
    raise ValueError("PRINTER_IP is not set. Please set the PRINTER_IP environment variable.")
PRINTER_VIDEO_URL = os.environ.get("PRINTER_VIDEO_URL", f"http://{PRINTER_IP}:3031/video")
MAINBOARD_ID = os.environ.get("MAINBOARD_ID")

if not MAINBOARD_ID:
    raise ValueError("MAINBOARD_ID is not set. Please set the MAINBOARD_ID environment variable.")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 60))
FAILURE_THRESHOLD = int(os.environ.get("FAILURE_THRESHOLD", 5))
CONFIDENCE_THRESHOLD = int(os.environ.get("CONFIDENCE_THRESHOLD", 80))
MODEL_NAME = os.environ.get("MODEL_NAME", "moondream")

# Ensure failure directory exists for debugging/review
FAILURES_DIR = "/app/failures"
os.makedirs(FAILURES_DIR, exist_ok=True)

PROMPT = (
    "Analyze this image of a 3D print in progress. "
    "Is the print failing? Look for spaghetti (tangled mess of filament), "
    "a detached object, or a large blob of filament on the nozzle. "
    "Respond with a confidence score from 0 to 100, where 100 is certain failure and 0 is perfectly fine. "
    "Answer only with the number."
)

consecutive_failures = 0

def sdcp_request(payload=None, timeout=10):
    """Sends a raw WebSocket request to the SDCP API and returns the first response."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((PRINTER_IP, 3030))
        
        # Simple WebSocket handshake
        handshake = (
            "GET /websocket HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(PRINTER_IP)
        sock.send(handshake.encode())
        
        # Read handshake response
        handshake_resp = b""
        while b"\r\n\r\n" not in handshake_resp:
            chunk = sock.recv(1024)
            if not chunk: break
            handshake_resp += chunk
        
        if payload:
            # We'll just send it as a raw string if it's not working, but WS usually needs framing.
            # However, some ChiTu boards are lax. 
            # If it fails, we might need a real WS library.
            # Let's try sending it as a text frame (0x81 + length)
            msg = json.dumps(payload).encode()
            header = bytearray([0x81])
            if len(msg) <= 125:
                header.append(len(msg))
            else:
                # Basic framing for larger messages not needed for simple pause
                header.append(126)
                header.extend(len(msg).to_bytes(2, 'big'))
            sock.send(header + msg)
        
        # Read responses (loop a bit until we see a '{')
        data = b""
        for _ in range(5): # Try reading up to 5 times
            chunk = sock.recv(8192)
            if not chunk: break
            data += chunk
            if b"{" in data: break
            time.sleep(0.5)
            
        sock.close()
        
        # Extract JSON
        try:
            start = data.find(b'{')
            end = data.rfind(b'}')
            if start != -1 and end != -1:
                return json.loads(data[start:end+1].decode('utf-8', errors='ignore'))
        except:
            pass
        return None
    except Exception as e:
        return None

def is_printer_printing():
    """Check if the printer is printing via SDCP."""
    # Try a few times because status broadcasts are periodic
    for _ in range(3):
        status = sdcp_request(None, timeout=5)
        if status and "Status" in status:
            s_obj = status["Status"]
            print_status = s_obj.get("CurrentStatus", [0])
            
            # On Centauri Carbon (SDCP v3), CurrentStatus [1] can mean Printing OR Paused.
            # PrintInfo["Status"] == 13 is actively printing.
            # PrintInfo["Status"] == 6 is paused/stopped.
            if isinstance(print_status, list):
                is_active = 1 in print_status
            else:
                is_active = print_status == 1
                
            if is_active:
                p_info_status = s_obj.get("PrintInfo", {}).get("Status")
                # 13 is printing. If it's 6 or something else, it's likely paused/stopped.
                return p_info_status == 13
            
            return False
        time.sleep(1)
    return False

def pause_printer():
    """Send SDCP pause command using V3 protocol."""
    print("CRITICAL: Threshold reached. Pausing the printer!")
    import uuid
    payload = {
        "Id": uuid.uuid4().hex,
        "Data": {
            "Cmd": 1,
            "Data": {
                "Type": 1 # 1 is Pause
            },
            "RequestID": str(uuid.uuid4()),
            "MainboardID": MAINBOARD_ID,
            "TimeStamp": int(time.time() * 1000)
        },
        "Topic": f"sdcp/request/{MAINBOARD_ID}"
    }
    sdcp_request(payload)
    print("Pause command sent.")

def capture_screenshot(output_path="current_frame.jpg"):
    command = [
        'ffmpeg',
        '-i', PRINTER_VIDEO_URL,
        '-ss', '0.5',
        '-frames:v', '1',
        '-q:v', '2',
        output_path,
        '-y'
    ]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Failed to capture screenshot: {e}")
        return False

def ensure_model_pulled():
    """Check if Ollama has the model, pull if not."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        models = [m['name'] for m in resp.json().get('models', [])]
        if any(MODEL_NAME in m for m in models):
            print(f"Model '{MODEL_NAME}' is ready.")
            return True
        
        print(f"Model '{MODEL_NAME}' not found. Pulling... (this may take a while)")
        # Use stream=True to avoid buffering the whole thing if it's large
        with requests.post(f"{OLLAMA_URL}/api/pull", json={"name": MODEL_NAME}, stream=True, timeout=600) as r:
            for line in r.iter_lines():
                if line:
                    # Just to keep it alive
                    pass
        return True
    except Exception as e:
        print(f"Error checking/pulling model: {e}")
        return False

def analyze_image_with_ollama(image_path):
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        payload = {
            "model": MODEL_NAME,
            "prompt": PROMPT,
            "stream": False,
            "images": [encoded_string]
        }
        
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=60)
        resp.raise_for_status()
        
        response_text = resp.json().get("response", "").strip()
        if not response_text:
            print("WARNING: Ollama returned an empty response. Ignoring.")
            return False

        # Attempt to parse as integer
        try:
            # Clean non-digit characters just in case it's verbose
            import re
            score_match = re.search(r'\d+', response_text)
            if score_match:
                confidence = int(score_match.group())
                print(f"Ollama failure confidence: {confidence}% (Threshold: {CONFIDENCE_THRESHOLD}%)")
                return confidence >= CONFIDENCE_THRESHOLD
            else:
                print(f"WARNING: No numeric confidence found in response: {response_text}")
                return False
        except Exception as e:
            print(f"Error parsing Ollama response '{response_text}': {e}")
            return False
    except Exception as e:
        print(f"Error communicating with Ollama: {e}")
        return False

def main_loop():
    global consecutive_failures
    print(f"Starting print watcher for Centauri Carbon...")
    
    # Wait for Ollama to be ready
    for _ in range(12): # Wait up to 60s
        try:
            requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
            break
        except:
            time.sleep(5)
            
    ensure_model_pulled()
    
    while True:
        try:
            if is_printer_printing():
                print(f"[{datetime.now().isoformat()}] Printer is active. Capturing frame...")
                
                screenshot_path = "current_frame.jpg"
                if capture_screenshot(screenshot_path):
                    is_failing = analyze_image_with_ollama(screenshot_path)
                    
                    if is_failing:
                        consecutive_failures += 1
                        print(f"WARNING: Potential failure detected! ({consecutive_failures}/{FAILURE_THRESHOLD})")
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        shutil.move(screenshot_path, os.path.join(FAILURES_DIR, f"fail_{timestamp}.jpg"))
                        
                        if consecutive_failures >= FAILURE_THRESHOLD:
                            pause_printer()
                            consecutive_failures = 0
                    else:
                        consecutive_failures = 0
                
        except Exception as e:
            print(f"Loop error: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main_loop()
