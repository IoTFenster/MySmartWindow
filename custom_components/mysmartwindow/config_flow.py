import logging
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from .const import CLOUD_API_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

class MySmartWindowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración para MySmartWindow."""

    async def async_step_user(self, user_input=None):
        """Primer paso de configuración."""
        errors = {}

        schema = vol.Schema({
            vol.Required("cloud_token"): str,
        })

        if user_input is not None:
            cloud_token = user_input.get("cloud_token")
            devices = await self.get_cloud_devices(cloud_token)

            if devices is None:
                errors["base"] = "invalid_token"  # Muestra un error si la autenticación falla.
            else:
                return self.async_create_entry(
                    title="MySmartWindow",
                    data={"cloud_token": cloud_token, "devices": devices},
                )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def get_cloud_devices(self, cloud_token):
        """Obtener dispositivos desde la nube usando aiohttp."""
        try:
            headers = {"Authorization": f"Bearer {cloud_token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(CLOUD_API_URL, headers=headers, timeout=60) as response:
                    if response.status == 401:
                        _LOGGER.error("Token inválido. Verifica tus credenciales.")
                        return None

                    response.raise_for_status()
                    data = await response.json()
                    return data.get("Remote_Data", {}).get("Creator_Buildings", [])
        except Exception as e:
            _LOGGER.error("Error obteniendo dispositivos: %s", e)
            return None
