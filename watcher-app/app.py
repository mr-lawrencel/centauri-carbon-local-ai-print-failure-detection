import os
import time
import shutil
import logging
import requests
from datetime import datetime

from config import Config
from sdcp_client import is_printer_printing, pause_printer
from vision import capture_screenshot, analyze_image_with_ollama, ensure_model_pulled

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

os.makedirs(Config.FAILURES_DIR, exist_ok=True)

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
                consecutive_failures = 0
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
        time.sleep(Config.CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Watcher stopped by user.")
