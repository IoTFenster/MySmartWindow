import logging
import asyncio
import json
import re
from homeassistant.components.light import LightEntity, ColorMode, ATTR_RGB_COLOR
from .const import DOMAIN, COMMANDS, SOCKET_PORT
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=15)

# Mapeo de colores a números (1-8)
COLOR_MAP = {
    1: (255, 0, 0),     # Rojo
    2: (255, 255, 0),   # Amarillo
    3: (0, 128, 0),     # Verde
    4: (255, 165, 0),   # Naranja
    5: (255, 255, 255), # Blanco
    6: (0, 0, 255),     # Azul
    7: (128, 0, 128),   # Violeta
    8: (255, 192, 203)  # Rosa
}

# Inverso para buscar el número desde RGB
REVERSE_COLOR_MAP = {v: k for k, v in COLOR_MAP.items()}

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configurar luces en función de los datos obtenidos de la API."""
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
                if "S9" in window.get("Services", []):
                    device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, window_name)},
                    manufacturer="MySmartWindow",
                    model="Smart Light",
                    name=f"{room_name} - {window.get('Name', 'Ventana Desconocida')}",
                    sw_version="1.0",
                    )
                    devices.append(MySmartLight(window, home, room_name))

    if devices:
        async_add_entities(devices, update_before_add=True)
    else:
        _LOGGER.warning("No se encontraron LEDs con servicio S9 para agregar a Home Assistant.")

class MySmartLight(LightEntity):
    """Entidad de Home Assistant para un LED RGB Smart."""

    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB  # 🔹 CORRECCIÓN: Definir color mode correctamente
    
    def __init__(self, window, home, room_name):
        """Inicializar LED RGB."""
        self._window = window
        self._room_name = room_name
        self._attr_name = f"{room_name} - {window.get('Name', 'LED Desconocido')}"
        self._attr_unique_id = window.get("Id_Window", None)
        self._host = window.get("Ip", "0.0.0.0")
        self._bearer = home.get("Bearer", "")
        self._color_number = 1  # Blanco por defecto
        self._attr_rgb_color = COLOR_MAP[self._color_number]
        self._attr_is_on = True  # Asumimos que está encendido al inicio
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "MySmartWindow",
            "model": "Smart Light",
        }

    async def send_command(self, command, args=None):
        """Enviar un comando al LED a través de socket."""
        try:
            reader, writer = await asyncio.open_connection(self._host, SOCKET_PORT)
            mensaje = {
                "bearer": self._bearer,
                "type": "plain",
                "op": COMMANDS[command]["op"]
            }
            if args:
                mensaje["args"] = args

            writer.write(json.dumps(mensaje).encode())
            await writer.drain()
            respuesta = await reader.read(1024)
            respuesta_decodificada = respuesta.decode().strip()
            writer.close()
            await writer.wait_closed()
            return respuesta_decodificada

        except Exception as e:
            _LOGGER.error("Error al enviar comando: %s", e)
            return None

    async def async_turn_on(self, **kwargs):
        """Encender el LED y asignar color si es necesario."""
        requested_color = kwargs.get(ATTR_RGB_COLOR)
        if requested_color:
            # Buscar el color más cercano en el mapa de colores permitidos
            closest_color = min(
                COLOR_MAP.values(), 
                key=lambda c: sum(abs(c[i] - requested_color[i]) for i in range(3))
            )
            self._color_number = REVERSE_COLOR_MAP[closest_color]
            self._attr_rgb_color = closest_color
            # Si el LED está apagado, primero lo encendemos antes de cambiar el color
            if not self._attr_is_on:
                await self.send_command("LED ON")
                self._attr_is_on = True
                await asyncio.sleep(0.5)  # Esperar un poco para asegurar que el LED se encienda
    
            # Enviar el comando de cambio de color solo si la luz está encendida
            await self.send_command("LED COLOR SELECTION", self._color_number)
    
        else:
            # Si no se especifica color, solo encender el LED
            if not self._attr_is_on:
                await self.send_command("LED ON")
                self._attr_is_on = True
    
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Apagar el LED."""
        await self.send_command("LED OFF")
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_update(self):
        """Obtener el estado inicial del LED."""
        try:
            datos = await self.send_command("LED STATE")
            if datos is None:
                _LOGGER.error("No se recibió una respuesta válida al actualizar estado del LED")
                return

            match = re.search(r"\{.*\}", datos.strip())
            if not match:
                _LOGGER.error("No se encontró JSON válido en la respuesta")
                return

            mensaje = json.loads(match.group(0))
            nuevo_estado = mensaje["value"]
            if nuevo_estado != self._attr_is_on:
                self._attr_is_on = nuevo_estado
                self.async_write_ha_state()
    
            # Consultar el estado del color si el LED está encendido
            if self._attr_is_on:
                color_estado = await self.send_command("LED COLOR STATE")
                if color_estado is None:
                    _LOGGER.error("No se recibió una respuesta válida al actualizar el estado del color del LED")
                    return
    
                match_color = re.search(r"\{.*\}", color_estado.strip())
                if not match_color:
                    _LOGGER.error("No se encontró JSON válido en la respuesta del color")
                    return
    
                mensaje_color = json.loads(match_color.group(0))
                color_numero = mensaje_color["value"]
                if color_numero != self._color_number:
                    self._color_number = color_numero
                    self._attr_rgb_color = COLOR_MAP.get(self._color_number, (255, 255, 255))
                    self.async_write_ha_state()
            self.async_write_ha_state()
    
        except Exception as e:
            _LOGGER.error("Error al obtener estado inicial: %s", e)

