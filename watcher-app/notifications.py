import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

class NotificationProvider:
    def send(self, message: str):
        raise NotImplementedError

class DiscordProvider(NotificationProvider):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: str):
        if not self.webhook_url:
            return
        try:
            payload = {"content": message}
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")

class NotificationManager:
    def __init__(self):
        self.providers = []
        if Config.DISCORD_WEBHOOK_URL:
            self.providers.append(DiscordProvider(Config.DISCORD_WEBHOOK_URL))

    def notify(self, message: str):
        logger.info(f"Notification: {message}")
        for provider in self.providers:
            provider.send(message)

# Singleton instance
notifier = NotificationManager()
