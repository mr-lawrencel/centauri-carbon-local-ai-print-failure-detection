import json
import time
import uuid
import logging
from websocket import create_connection, WebSocketException
from config import Config

logger = logging.getLogger(__name__)

def sdcp_request(payload=None, timeout=10):
    """Sends a request to the SDCP API using WebSocket and returns the response."""
    ws_url = f"ws://{Config.PRINTER_IP}:3030/websocket"
    ws = None
    try:
        ws = create_connection(ws_url, timeout=timeout)
        
        if payload:
            ws.send(json.dumps(payload))
        
        for _ in range(5):
            try:
                result = ws.recv()
                if not result:
                    continue
                
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
            
            is_active = (1 in print_status) if isinstance(print_status, list) else (print_status == 1)
                
            if is_active:
                p_info_status = s_obj.get("PrintInfo", {}).get("Status")
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
                "Type": 1
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
