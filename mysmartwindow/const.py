DOMAIN = "mysmartwindow"

# URLs de la API en la nube
CLOUD_API_URL = "https://www.mysmartwindow.com:33332/hope/v3/users/buildings"

# Configuración de la API
POLLING_INTERVAL = 15  # En segundos
HEADERS = {"Content-Type": "application/json"}

# Códigos de operación para los dispositivos
COMMANDS = {
    "LED ON": {"op": 60},
    "LED OFF": {"op": 61},
    "LED STATE": {"op": 66},
    "LED COLOR SELECTION": {"op": 65},
    "LED COLOR STATE": {"op": 68},
    "WINDOW OPEN": {"op": 54},
    "WINDOW CLOSE": {"op": 53},
    "WINDOW STATE": {"op": 55},
    "WINDOW MICRO OPEN": {"op": 73},
    "WINDOW MICRO STATE": {"op": 74},
    "BLIND UP": {"op": 7},
    "BLIND DOWN": {"op": 8},
    "BLIND STOP": {"op": 9},
    "BLIND STATE": {"op": 6},
    "BLIND POSITION UNIT": {"op": 63},
    "TEMPERATURE": {"op": 4},
    "HUMEDITY": {"op": 5},
    "Co2": {"op": 58},
    "VOC": {"op": 59},
    "IAQ": {"op": 71},
    "BAROMETRO": {"op": 72},
    "OP_SENSORS": {"op": 62}
}

# Puerto para comunicación por socket (si aplica)
SOCKET_PORT = 443