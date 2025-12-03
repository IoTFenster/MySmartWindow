import logging
import asyncio
import json
import re
from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from .const import DOMAIN, COMMANDS
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configurar persianas en función de los datos obtenidos de la API."""
    devices = []
    raw_data = hass.data[DOMAIN].get("devices", [])

    if not isinstance(raw_data, list) or not raw_data:
        return
    
    device_registry = async_get_device_registry(hass)
    
    for building in raw_data:
        home = building.get("Home", {})
        rooms = home.get("Rooms", [])
        for room in rooms:
            room_name = room.get("Name", "Sala Desconocida")
            windows = room.get("Windows", []) or []
            _LOGGER.warning("windows: %s", windows)
            for window in windows:
                window_name = window.get("Name", "Ventana desconocida")
                if not isinstance(window, dict):
                    continue
                # Registrar dispositivo en HA
                device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, window_name)},
                    manufacturer="MySmartWindow",
                    model="Smart Cover",
                    name=f"{room_name} - {window.get('Name', 'Ventana Desconocida')}",
                    sw_version="1.0",
                )
                devices.append(MySmartWindowCover(window, home, room_name))

    if devices:
        async_add_entities(devices)
    else:
        _LOGGER.warning("No se encontraron ventanas válidas para agregar a Home Assistant.")

class MySmartWindowCover(CoverEntity):
    """Entidad de Home Assistant para una ventana MySmartWindow."""

    def __init__(self, window, home, room_name):
        """Inicializar ventana."""
        self._window = window
        self._room_name = room_name
        self._attr_name = f"{room_name} - {window.get('Name', 'Ventana Desconocida')}"
        self._attr_unique_id = window.get("Id_Window", None)
        self._ip = window.get("Ip", "0.0.0.0")
        self._port = 443  # Cambia esto si el dispositivo usa otro puerto
        self._attr_is_closed = False
        self._bearer = home.get("Bearer", "")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "MySmartWindow",
            "model": "Smart Cover",
        }

        # Estado inicial.
        self._current_position = 0  # Posición inicial de la persiana (0-100)
        self._attr_is_opening = False
        self._attr_is_closing = False
        self._attr_is_closed = None  # Se actualizará con `async_update`
    
    @property
    def supported_features(self):
        """Indicar a Home Assistant que la persiana soporta control de posición, abrir y cerrar."""
        return (
        CoverEntityFeature.OPEN |
        CoverEntityFeature.CLOSE |
        CoverEntityFeature.STOP |
        CoverEntityFeature.SET_POSITION
        )
        
    @property
    def state(self):
        """Devuelve el estado de la persiana ('closed' o 'open') según su posición."""
        return "closed" if self._current_position == 0 else "open"
        
    @property
    def current_position(self):
        """Devuelve la posición actual en 0-100 invirtiendo la escala (0 cerrado, 100 abierto)."""
        if self._current_position is None:
            return 50  # Valor por defecto
        else:
            return self._current_position
            #return 100 - (self._current_position / 120 * 100)
        
    
    async def send_command(self, command, position=None):
        """Enviar un comando a la ventana usando socket en formato JSON."""
        if command not in COMMANDS:
            _LOGGER.error("Comando desconocido: %s", command)
            return
    
        # Construcción del mensaje JSON
        auth_header = {
            #"bearer":f"{self._bearer}",
            "bearer": self._bearer,
            "type": "plain",
            "op": COMMANDS[command]["op"]
        }
        
        if position is not None:
            auth_header["args"] = position  # Enviar posición si se requiere

        message = json.dumps(auth_header)  # Convertimos el diccionario a JSON
    
        try:
            reader, writer = await asyncio.open_connection(self._ip, self._port)
            
            writer.write(message.encode())  # Enviar mensaje JSON
            await writer.drain()
            
            data = await reader.read(1024)  # Leer la respuesta del dispositivo
            response = data.decode().strip()
            
            writer.close()
            await writer.wait_closed()
            
            return response  # Devolvemos la respuesta para posibles validaciones
            
        except Exception as e:
            _LOGGER.error("Error enviando comando -> send_command a %s: %s", self._attr_name, e)
            return None
    
    async def async_open_cover(self, **kwargs):
        """Subir la persiana."""
        _LOGGER.warning("Subiendo persiana: %s", self._attr_name)
        await self.send_command("BLIND UP")
        self._attr_is_opening = True
        self._attr_is_closing = False
        self.async_write_ha_state()
        await self.async_update()  # Refresca el estado después de ejecutar el comando

    async def async_close_cover(self, **kwargs):
        """Bajar la persiana."""
        _LOGGER.warning("Bajando persiana: %s", self._attr_name)
        await self.send_command("BLIND DOWN")
        self._attr_is_closing = True
        self._attr_is_opening = False
        self.async_write_ha_state()
        await self.async_update()  # Refresca el estado después de ejecutar el comando

    async def async_stop_cover(self, **kwargs):
        """Detener la persiana."""
        _LOGGER.warning("Deteniendo persiana: %s", self._attr_name)
        await self.send_command("BLIND STOP")
        self._attr_is_opening = False
        self._attr_is_closing = False
        self.async_write_ha_state()
        await self.async_update()  # Refresca el estado después de ejecutar el comando

    async def async_set_cover_position(self, **kwargs):
        """Ajustar la posición de la persiana."""
        position = kwargs.get("position", 0)
        if position is None or not (0 <= position <= 100):
            _LOGGER.error(" Posición inválida: %s", position)
            return

        # Convertir de 0-100 (HA) a 120-0 (persiana)
        adjusted_position = int((100 - position) * 1.2)  
        
        await self.send_command("BLIND POSITION UNIT", adjusted_position)
        
        self._current_position = adjusted_position
        self.async_write_ha_state()
        await self.async_update()  # Refresca el estado después de ejecutar el comando
        self.async_write_ha_state()
        
    async def async_update(self):
        """Obtener la posición actual de la persiana y actualizar la UI."""
        try:
            response = await self.send_command("BLIND STATE")
    
            if not response:
                _LOGGER.error("No se recibió respuesta de BLIND STATE.")
                return  # Evitar cambiar el estado si no hay datos
    
            # Intentar extraer solo el primer objeto JSON válido
            match = re.search(r"\{.*\}", response.strip())
    
            if not match:
                _LOGGER.error("No se encontró un JSON válido en la respuesta: %s", response)
                return  # Evitar sobrescribir el estado con un valor incorrecto
    
            response_json = match.group(0)
    
            try:
                mensaje = json.loads(response_json)  # Convertir en diccionario
                _LOGGER.warning(" JSON decodificado correctamente: %s", mensaje)
    
                if isinstance(mensaje, dict) and "value" in mensaje:
                    try:
                        position_120 = int(mensaje["value"])  # Convertir a entero
                        new_position = int(100 - (position_120 / 120 * 100))  # Convertir de 120-0 a 0-100
                        
                        # Solo actualizar si el valor es válido
                        if 0 <= new_position <= 100:
                            if new_position != self._current_position:
                                self._current_position = new_position
                                self._attr_extra_state_attributes = {"current_position": self._current_position}
                                self.async_write_ha_state()
                            else:
                                _LOGGER.info("Estado sin cambios.")
                    except (ValueError, TypeError) as e:
                        _LOGGER.error("Error al procesar 'value': %s | Respuesta: %s", e, mensaje)
                        
                else:
                    _LOGGER.error("No se encontró 'value' en la respuesta BLIND STATE: %s", mensaje)
                    
            except json.JSONDecodeError as e:
                _LOGGER.error("Error al decodificar JSON: %s | Respuesta: %s", e, response_json)
                
        except Exception as e:
            _LOGGER.error("Error obteniendo estado de %s: %s", self._attr_name, e)


