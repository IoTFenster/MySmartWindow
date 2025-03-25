import logging
import asyncio
import json
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN,COMMANDS
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configura los sensores para MySmartWindow."""
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
                
                window_name = window.get("Name", "Ventana Desconocida")
                sensors = window.get("Sensors", [])
                if not isinstance(sensors, list):
                    sensors = []
                for sensor in sensors:
                    device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, window_name)},
                    manufacturer="MySmartWindow",
                    model="Smart Cover",
                    name=f"{room_name} - {window.get('Name', 'Ventana Desconocida')}",
                    sw_version="1.0",
                    )
                    devices.append(MySmartWindowSensor(window, sensor, room_name, home, window_name))
    if devices:
        async_add_entities(devices, update_before_add=True)
    else:
        _LOGGER.warning("No se encontraron sensores válidos para agregar a Home Assistant.")

class MySmartWindowSensor(SensorEntity):
    """Entidad de sensor para MySmartWindow."""

    def __init__(self, window, sensor, room_name, home, window_name):
        """Inicializa el sensor."""
        self._window = window
        self._sensor = sensor
        self._room_name = room_name
        self._home = home
        self._window_name = window_name
        self._attr_name = f"{room_name} - {window_name} - Sensor {sensor.get('Op', 'Desconocido')}"
        self._state = sensor.get("Value", "unknown")
        self._ip = window.get("Ip", "0.0.0.0")
        self._port = 443  # Puerto del socket TCP
        self._bearer = home.get("Bearer", "")
        self._attr_unique_id = f"{self._ip}-{sensor.get('Op', 'unknown')}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._attr_name,
            "manufacturer": "MySmartWindow",
            "model": "Smart Cover",
        }
        
    @property
    def unique_id(self):
        """Devuelve un ID único para el sensor."""
        return self._attr_unique_id

    @property
    def state(self):
        """Devuelve el estado actual del sensor."""
        return self._state
        
    async def async_update(self):
        """Actualizar el valor del sensor desde el dispositivo."""
        try:
            updated_value = await self._get_updated_value()
            
            if updated_value is not None:
                self._state = updated_value
                self.async_write_ha_state()  # 📝 Asegura que el estado se actualiza en la UI
                
        except Exception as e:
            _LOGGER.error("Error actualizando sensor %s: %s", self._attr_name, e)
            
    async def _get_updated_value(self):
        """Obtener el valor actualizado del sensor usando socket TCP."""
        message = json.dumps({
            "bearer": self._bearer,
            "type": "plain",
            "op": self._sensor["Op"]
        }) + "\n" 
    
        try:
            # Intentar conexión con timeout
            reader, writer = await asyncio.wait_for(asyncio.open_connection(self._ip, self._port), timeout=10)
    
            writer.write(message.encode())  
            await writer.drain()  # Asegura que el mensaje se envió completamente
            
            data = await reader.read(1000)  # Leer respuesta
            
            response = data
            
            response = response.replace(b'\x00', b'').strip()
            
            writer.close()
            
            await writer.wait_closed()  # Cierra la conexión correctamente
            # 🔹 Intentar parsear JSON
            try:
                
                response_json = json.loads(response.decode()) 
                 
                if "value" in response_json:
                    return response_json["value"]
                else:
                    return self._sensor.get("Value", STATE_UNKNOWN)
    
            except json.JSONDecodeError:
                _LOGGER.error("Error al decodificar JSON: %s", response)
                return self._sensor.get("Value", STATE_UNKNOWN)
    
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout al conectar con %s:%d", self._ip, self._port)
        except Exception as e:
            _LOGGER.error("Error obteniendo valor del sensor %s: %s", self._attr_name, e)
    
        return self._sensor["value"]  # Devuelve el último valor conocido si falla