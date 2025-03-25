import logging
import asyncio
import json
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from .const import DOMAIN, COMMANDS, SOCKET_PORT
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configurar switches en función de los datos obtenidos de la API."""
    devices = []
    raw_data = hass.data[DOMAIN].get("devices", [])

    if not isinstance(raw_data, list) or not raw_data:
        _LOGGER.error("Estructura inesperada de los dispositivos: %s", type(raw_data))
        return
    
    device_registry = async_get_device_registry(hass)
    
    for building in raw_data:
        home = building.get("Home", {})
        rooms = home.get("Rooms", [])

        for room in rooms:
            room_name = room.get("Name", "Sala Desconocida")
            windows = room.get("Windows", []) or []

            for window in windows:
                window_name = window.get("Name", "Ventana desconocida")
                if "S5" in window.get("Services", []):
                    device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, window_name)},
                    manufacturer="MySmartWindow",
                    model="Smart Cover",
                    name=f"{room_name} - {window.get('Name', 'Ventana Desconocida')}",
                    sw_version="1.0",
                    )
                    devices.append(MySmartWindowSwitch(window, home, room_name))

    if devices:
        async_add_entities(devices)
    else:
        _LOGGER.warning("No se encontraron ventanas inteligentes con servicio S1 para agregar a Home Assistant.")

class MySmartWindowSwitch(SwitchEntity):
    """Entidad de Home Assistant para una ventana inteligente."""

    def __init__(self, window, home, room_name):
        """Inicializar la ventana inteligente."""
        self._window = window
        self._room_name = room_name
        self._attr_name = f"{room_name} - {window.get('Name', 'Ventana Desconocida')}"
        self._attr_unique_id = window.get("Id_Window", None)
        self._host = window.get("Ip", "0.0.0.0")
        self._bearer = home.get("Bearer", "")
        self._attr_is_on = False  # False = Cerrado, True = Abierto
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "MySmartWindow",
            "model": "Smart Switch",
        }

    async def send_command(self, command):
        """Enviar un comando a la ventana a través de socket."""
        try:
            reader, writer = await asyncio.open_connection(self._host, SOCKET_PORT)
            mensaje = {
                "bearer": self._bearer,
                "type": "plain",
                "op": COMMANDS[command]["op"]
            }
            writer.write(json.dumps(mensaje).encode())
            await writer.drain()
            respuesta = await reader.read(1024)
            respuesta_decodificada = respuesta.decode().strip()
            writer.close()
            await writer.wait_closed()
            return respuesta_decodificada
        except Exception as e:
            _LOGGER.error("Error al enviar comando: %s", e)

    async def async_turn_on(self, **kwargs):
        """Abrir la ventana."""
        self._attr_is_on = True
        await self.send_command("WINDOW OPEN")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Cerrar la ventana."""
        self._attr_is_on = False
        await self.send_command("WINDOW CLOSE")
        self.async_write_ha_state()
            
    async def async_update(self):
        """Actualizar el estado de la ventana leyendo su estado actual."""
        try:
            datos = await self.send_command("WINDOW STATE")
            match = re.search(r"\{.*\}", datos.strip())
            if not match:
                _LOGGER.error("No se encontró JSON válido en la respuesta")
                return
            mensaje = json.loads(match.group(0))
            nuevo_estado = mensaje["value"]
            if nuevo_estado != self._attr_is_on:
                self._attr_is_on = nuevo_estado
                self.async_write_ha_state()
    
            # Notificar a Home Assistant sobre el cambio de estado
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error al actualizar estado de la ventana: %s", e)
