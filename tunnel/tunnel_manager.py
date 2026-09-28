"""
Tunnel Manager for Voice Agent Remote Access.
Establishes secure public HTTPS tunnel via ngrok, announces URL,
and writes connection details to remote_url.txt.
"""

import logging
import socket
from pathlib import Path
from typing import Optional
from config import config

logger = logging.getLogger("VoiceAgent.Tunnel")


class TunnelManager:
    def __init__(self, port: Optional[int] = None):
        self.port = port or config.SERVER_PORT
        self.public_url: Optional[str] = None
        self._tunnel = None

    def get_local_url(self) -> str:
        """Determine local Wi-Fi / LAN IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return f"http://{ip}:{self.port}"
        except Exception:
            return f"http://localhost:{self.port}"

    def start_tunnel(self) -> Optional[str]:
        """Start ngrok tunnel if auth token is present."""
        if not config.NGROK_AUTH_TOKEN:
            logger.info("NGROK_AUTH_TOKEN not configured. Remote public tunnel will not be started.")
            return None

        try:
            from pyngrok import ngrok
            ngrok.set_auth_token(config.NGROK_AUTH_TOKEN)
            self._tunnel = ngrok.connect(self.port, "http")
            self.public_url = self._tunnel.public_url
            logger.info(f"Ngrok public tunnel established: {self.public_url}")

            # Save to file
            url_file = config.BASE_DIR / "remote_url.txt"
            with open(url_file, "w", encoding="utf-8") as f:
                f.write(f"Public URL: {self.public_url}\nLocal LAN URL: {self.get_local_url()}\n")

            return self.public_url
        except Exception as e:
            logger.error(f"Failed to start ngrok tunnel: {e}")
            return None

    def stop_tunnel(self):
        """Disconnect active ngrok tunnel."""
        if self._tunnel:
            try:
                from pyngrok import ngrok
                ngrok.disconnect(self._tunnel.public_url)
                logger.info("Ngrok tunnel closed.")
            except Exception as e:
                logger.warning(f"Error disconnecting tunnel: {e}")
            self._tunnel = None
            self.public_url = None
