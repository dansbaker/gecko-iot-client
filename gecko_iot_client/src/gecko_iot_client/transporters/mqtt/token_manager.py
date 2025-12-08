"""Token manager for JWT token parsing and expiry tracking."""

import base64
import json
import logging
import urllib.parse
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages JWT token parsing, expiry tracking, and refresh timing."""

    def __init__(self, broker_url: str, refresh_buffer_seconds: int):
        self._broker_url = broker_url
        self._refresh_buffer = refresh_buffer_seconds
        self._current_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._parse_token()

    def _parse_token(self) -> None:
        """Parse JWT token from broker URL to extract expiry."""
        try:
            parsed_url = urllib.parse.urlparse(self._broker_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            token = query_params.get("token", [None])[0]

            if not token:
                return

            # Decode JWT payload (second part of token)
            parts = token.split(".")
            if len(parts) < 2:
                logger.warning("Invalid JWT token format")
                return

            # Decode payload with padding
            payload_part = parts[1]
            payload_part += "=" * (4 - len(payload_part) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_part)
            payload_json = json.loads(payload_bytes)

            # Check for expiry timestamp (support both standard 'exp' and Gecko's 'expiresAt')
            exp_timestamp = payload_json.get("exp") or payload_json.get("expiresAt")
            
            if exp_timestamp:
                # Handle milliseconds (if value is very large, it's likely in milliseconds)
                if exp_timestamp > 10000000000:  # Timestamp is in milliseconds
                    exp_timestamp = exp_timestamp / 1000.0
                    
                self._token_expiry = datetime.fromtimestamp(exp_timestamp)
                self._current_token = token
                logger.info(f"Token expires at: {self._token_expiry}")
            else:
                logger.warning("JWT token does not contain expiry claim")

        except Exception as e:
            logger.warning(f"Failed to parse token expiry: {e}")

    def update_broker_url(self, new_broker_url: str) -> None:
        """Update broker URL and re-parse token."""
        self._broker_url = new_broker_url
        self._parse_token()

    def is_expired(self) -> bool:
        """Check if token is currently expired."""
        if not self._token_expiry:
            return False
        return datetime.now() >= self._token_expiry

    def should_refresh(self, is_connected: bool) -> bool:
        """Check if token should be refreshed based on expiry buffer."""
        if not self._token_expiry or not is_connected:
            return False
        time_to_expiry = self._token_expiry - datetime.now()
        return time_to_expiry.total_seconds() <= self._refresh_buffer

    def force_expiry(self) -> None:
        """Force token to be expired (for handling authorization failures)."""
        self._token_expiry = datetime.now()

    @property
    def expiry(self) -> Optional[datetime]:
        """Get token expiry datetime."""
        return self._token_expiry
