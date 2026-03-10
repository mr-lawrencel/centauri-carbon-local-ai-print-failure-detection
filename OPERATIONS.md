# Print Watcher Operations Guide

This guide contains essential commands for managing the Centauri Carbon AI failure detection system.

## 🚀 Lifecycle Management
Run these from `/home/klipper/print-watcher`.

| Goal | Command | When to use |
| :--- | :--- | :--- |
| **Start everything** | `docker compose up -d` | Initial setup or after a reboot. |
| **Stop everything** | `docker compose down` | When you want to completely stop the services. |
| **Update/Restart App** | `docker compose up -d --build watcher` | Use this after modifying `app.py` or `requirements.txt`. |
| **Restart Services** | `docker compose restart` | Quick refresh if something seems "stuck". |

---

## 📊 Monitoring & Logs

### View Real-time Analysis
To see what the AI is thinking and if it's successfully talking to the printer:
```bash
docker compose logs -f watcher
```

### Check AI Service Health
To ensure Ollama is responding and see its internal logs:
```bash
docker compose logs -f ollama
```

### Verify GPU Acceleration
Since this uses NVIDIA, check if the container is actually seeing the GPU:
```bash
nvidia-smi
```

---

## 🛠 Debugging & Manual Checks

### List Pulled AI Models
Verify that `moondream` is correctly loaded in the AI container:
```bash
docker exec print_ai ollama list
```

### Manual Printer Status Check
Test the SDCP connection to the printer manually from within the container:
```bash
docker exec print_watcher python -c "from sdcp_client import is_printer_printing; print('Is Printing:', is_printer_printing())"
```

### Run Unit Tests
To verify the vision and parsing logic:
```bash
docker exec print_watcher python3 -m unittest discover -s /app/tests -p "test_*.py"
```

*(Note: In the container, you might need to adjust the path if the tests are mounted differently)*

### View Captured Failures
Check the directory where the system saves images that triggered a "YES" response:
```bash
ls -lh ./failed_prints
```

---

## ⚙️ Configuration Adjustments

If you need to change settings, edit the `environment` section in `docker-compose.yml`:

1.  **Change Sensitivity**: Decrease `FAILURE_THRESHOLD` (e.g., to `2`) if it's too slow to react.
2.  **Change Frequency**: Decrease `CHECK_INTERVAL` (e.g., to `30`) for more frequent checks.
3.  **Update Printer IP**: Change `PRINTER_IP` if your router assigns a new address.

**After editing `docker-compose.yml`, always run:**
```bash
docker compose up -d
```

---

## 🔍 Troubleshooting Common Issues

*   **"SDCP Connection Error"**: Usually means the printer is off, on a different IP, or the network is congested.
*   **"ffmpeg failed"**: Check if you can open `http://<YOUR_PRINTER_IP>:3031/video` in your browser. If you can't see the video there, the watcher won't either.
*   **Ollama is slow**: Ensure no other heavy GPU processes are running on the host. Moondream is lightweight but still requires GPU memory.
