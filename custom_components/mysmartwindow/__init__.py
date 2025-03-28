import logging
import os
import yaml
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configurar la integración y registrar los dispositivos correctamente."""
    hass.data.setdefault(DOMAIN, {})

    # Guardamos los dispositivos en hass.data
    devices = entry.data.get("devices", [])
    hass.data[DOMAIN]["devices"] = devices
    _LOGGER.info("Dispositivos cargados en hass.data: %s", devices)

    async def handle_open_window(call):
        """Abrir la ventana."""
        entity_id = call.data.get("entity_id")
        _LOGGER.info("Abriendo ventana: %s", entity_id)

    async def handle_close_window(call):
        """Cerrar la ventana."""
        entity_id = call.data.get("entity_id")
        _LOGGER.info("Cerrando ventana: %s", entity_id)

    async_register_admin_service(hass, DOMAIN, "open_window", handle_open_window, schema=None)
    async_register_admin_service(hass, DOMAIN, "close_window", handle_close_window, schema=None)

    device_registry = async_get_device_registry(hass)

    # Registrar cada dispositivo en el sistema de dispositivos de HA
    for building in devices:
        home = building.get("Home", {})
        rooms = home.get("Rooms", [])
        for room in rooms:
            windows = room.get("Windows", []) or []
            for window in windows:
                window_id = window.get("Id_Window")
                if not window_id:
                    continue
                device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, window_id)},
                    manufacturer="MySmartWindow",
                    model="Smart Cover",
                    name=f"{room.get('Name', 'Sala Desconocida')} - {window.get('Name', 'Ventana Desconocida')}",
                    sw_version="1.0",
                )
                
    await hass.config_entries.async_forward_entry_setups(entry, ["cover", "sensor", "light", "switch"])
    
    return True
    
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Desinstalar la integración."""
    _LOGGER.info("Desinstalando integración MySmartWindow")
    
    if DOMAIN in hass.data:
        hass.data.pop(DOMAIN)
    
    return await hass.config_entries.async_unload_platforms(entry, ["cover", "sensor", "light", "switch"])
