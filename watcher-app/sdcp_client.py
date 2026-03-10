import json
import time
import uuid
import logging
from websocket import create_connection, WebSocketException, WebSocketTimeoutException
from config import Config

logger = logging.getLogger(__name__)

class SDCPClient:
    def __init__(self, ip, timeout=10):
        self.ip = ip
        self.timeout = timeout
        self.ws_url = f"ws://{ip}:3030/websocket"
        self.ws = None

    def connect(self):
        """Establishes a WebSocket connection to the printer."""
        try:
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
            self.ws = create_connection(self.ws_url, timeout=self.timeout)
            logger.debug(f"Connected to SDCP at {self.ws_url}")
            return True
        except Exception as e:
            logger.debug(f"Failed to connect to SDCP: {e}")
            self.ws = None
            return False

    def is_connected(self):
        """Checks if the WebSocket connection is active."""
        return self.ws is not None and self.ws.connected

    def request(self, payload=None, retries=2):
        """Sends a request and waits for a response, with automatic reconnection."""
        for attempt in range(retries + 1):
            if not self.is_connected():
                if not self.connect():
                    time.sleep(1)
                    continue

            try:
                if payload:
                    self.ws.send(json.dumps(payload))
                
                # Wait for a valid JSON response
                for _ in range(5):
                    try:
                        result = self.ws.recv()
                        if not result:
                            continue
                        
                        start = result.find('{')
                        end = result.rfind('}')
                        if start != -1 and end != -1:
                            return json.loads(result[start:end+1])
                    except (json.JSONDecodeError, WebSocketException, WebSocketTimeoutException):
                        continue
                    time.sleep(0.1)
                return None

            except (WebSocketException, BrokenPipeError, ConnectionResetError) as e:
                logger.debug(f"SDCP connection lost during request: {e}")
                self.ws = None # Trigger reconnect on next attempt
                if attempt < retries:
                    time.sleep(0.5)
                    continue
                break
            except Exception as e:
                logger.error(f"Unexpected SDCP request error: {e}")
                break
        return None

    def close(self):
        """Closes the WebSocket connection."""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None

# Create a singleton instance for use throughout the app
client = SDCPClient(Config.PRINTER_IP)

def is_printer_printing():
    """Check if the printer is currently active and printing via SDCP."""
    for _ in range(3):
        status = client.request(None)
        if status and "Status" in status:
            s_obj = status["Status"]
            print_status = s_obj.get("CurrentStatus", [0])
            
            is_active = (1 in print_status) if isinstance(print_status, list) else (print_status == 1)
                
            if is_active:
                p_info_status = s_obj.get("PrintInfo", {}).get("Status")
                return p_info_status == 13
            
            return False
        time.sleep(0.5)
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
                "Type": 1
            },
            "RequestID": request_id,
            "MainboardID": Config.MAINBOARD_ID,
            "TimeStamp": int(time.time() * 1000)
        },
        "Topic": f"sdcp/request/{Config.MAINBOARD_ID}"
    }
    
    resp = client.request(payload)
    if resp:
        logger.info(f"Pause command sent. Response: {resp.get('Attributes', {}).get('Result', 'Sent')}")
    else:
        logger.error("Failed to confirm pause command receipt.")
