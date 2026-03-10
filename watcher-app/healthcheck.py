from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import logging
import time

logger = logging.getLogger(__name__)

# Global variable to track the last successful loop time
last_heartbeat = time.time()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global last_heartbeat
        # If the main loop hasn't updated the heartbeat in 3 times the check interval, 
        # we consider it unhealthy. We'll use a default of 300s as a safe buffer.
        if time.time() - last_heartbeat < 300:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(503)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Service Unavailable")

    def log_message(self, format, *args):
        # Suppress standard logging to keep container logs clean
        return

def update_heartbeat():
    global last_heartbeat
    last_heartbeat = time.time()

def start_health_check_server(port=8080):
    def run_server():
        server_address = ('', port)
        httpd = HTTPServer(server_address, HealthCheckHandler)
        logger.info(f"Health check server started on port {port}")
        httpd.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
