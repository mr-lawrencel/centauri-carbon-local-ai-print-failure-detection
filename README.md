# Centauri Carbon AI Print Watcher

An autonomous, locally-hosted 3D print failure detection system for the Centauri Carbon. This system uses local AI (via Ollama) to analyze your printer's video stream and automatically pauses the print if failure (spaghetti, blobs, or detachment) is detected.

## ✨ Why this project?
- **💰 100% Free**: No subscriptions, no hidden fees, no "pro" tiers.
- **🔒 Fully Private**: No images or data ever leave your local network. Everything runs on your machine.
- **🏠 Runs Locally**: No dependence on cloud services or internet connectivity for failure detection.
- **⚙️ Highly Configurable**: Fine-tune sensitivity, check frequency, and AI confidence to match your environment.

## 🚀 Features
- **Local AI Analysis**: Uses `moondream` or `llava` via Ollama.
- **Auto-Pause**: Sends a native SDCP "Pause" command to the printer when failure thresholds are met.
- **Failure Gallery**: Automatically saves images of detected failures to `./failed_prints` for later review or dataset building.
- **Smart Thresholds**: Requires multiple consecutive detections to prevent "false positive" pauses from temporary shadows or movement.

## 🛠 Hardware Requirements
- **Printer**: Centauri Carbon (tested). Should work with other SDCP v3 printers.
- **Host**: 
  - **NVIDIA GPU** (Recommended): Tested on GTX 1060.
  - **CPU/iGPU**: Works via Ollama's CPU fallback (slower, but functional for 60s intervals).

## 📦 Setup (Docker Compose) - Recommended
This is the easiest way to run the system as it handles all dependencies (ffmpeg, Python, etc.) automatically.

1. **Configure**: Open `docker-compose.yml` and set your variables:
   - `PRINTER_IP`: Your printer's local IP address.
   - `MAINBOARD_ID`: Found in your printer settings or via network discovery.
2. **Launch**:
   ```bash
   docker compose up -d
   ```
3. **Monitor**:
   ```bash
   docker compose logs -f watcher
   ```

## 🐍 Setup (Native Python) - Experimental
If you prefer to run without Docker:

1. **Prerequisites**: 
   - Install [Ollama](https://ollama.com/) and run `ollama pull moondream`.
   - Install `ffmpeg` on your system path.
2. **Install Dependencies**:
   ```bash
   pip install requests
   ```
3. **Run**:
   ```bash
   export PRINTER_IP="10.0.0.100"
   export MAINBOARD_ID="your_id_here"
   python watcher-app/app.py
   ```

## ⚙️ Configuration Variables
| Variable | Description | Default |
| :--- | :--- | :--- |
| `PRINTER_IP` | Your printer's local IP address. | **REQUIRED** |
| `MAINBOARD_ID` | Your printer's Mainboard ID (found in settings). | **REQUIRED** |
| `CHECK_INTERVAL` | Seconds between AI checks. | `60` |
| `FAILURE_THRESHOLD` | Consecutive detections needed to pause. | `5` |
| `CONFIDENCE_THRESHOLD` | AI confidence score (0-100) to trigger a "fail". | `80` |
| `MODEL_NAME` | Ollama model to use (`moondream` or `llava`). | `moondream` |

## 🤝 Contributing
I've only tested this on a **Centauri Carbon** and an **NVIDIA GTX 1060**. If you successfully use this with other printers or on an iGPU, please open an issue or PR to update the documentation!

## 📜 License
This project is licensed under the MIT License.
