"""API for Gecko bound to Home Assistant OAuth."""

from typing import Any
import logging
from abc import ABC, abstractmethod

from aiohttp import ClientSession

from .const import API_BASE_URL, AUTH0_BASE_URL

_LOGGER = logging.getLogger(__name__)


class GeckoApiClient(ABC):
    """Provide Gecko authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession
    ) -> None:
        """Initialize Gecko auth."""
        self.websession = websession

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token for the Gecko API."""

    async def async_get_user_id(self) -> dict[str, Any]:
        """Get user information from Auth0 or Gecko API."""
        token = await self.async_get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get from Auth0 userinfo
        url = f"{AUTH0_BASE_URL}/userinfo"
        async with self.websession.get(url, headers=headers) as response:
            response.raise_for_status()
            payload = await response.json()
            _LOGGER.debug("Fetched user info: %s", payload)
        try:
            return payload["sub"]
        except KeyError:
            raise ValueError("User ID ('sub') not found in Auth0 response: %s" % payload)
    
        
    async def async_request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> Any:
        """Make an authenticated request to the Gecko API."""
        access_token = await self.async_get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {access_token}"
        
        url = f"{API_BASE_URL}{endpoint}"
        
        async with self.websession.request(method, url, headers=headers, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def async_get_vessels(self, account_id: str) -> list[dict[str, Any]]:
        """Get available vessels for the account."""
        data = await self.async_request("GET", f"/v4/accounts/{account_id}/vessels")
        return data if isinstance(data, list) else []

    async def async_get_user_info(self, user_id: str) -> dict[str, Any]:

        access_token = await self.async_get_access_token()
        _LOGGER.debug("Fetching user info for user_id: %s", user_id)
        _LOGGER.debug("Using access token: %s", access_token)
        
        return await self.async_request("GET", f"/v2/user/{user_id}")


    async def async_get_monitor_livestream(self, monitor_id: str) -> dict[str, Any]:
        """Get MQTT livestream connection details for a monitor."""
        livestream_data = await self.async_request("GET", f"/v1/monitors/{monitor_id}/iot/thirdPartySession")
        _LOGGER.debug("Fetched livestream data for monitor %s", monitor_id)
        return livestream_data


