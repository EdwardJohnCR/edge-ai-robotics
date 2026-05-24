Python
import requests
import time

# REEMPLAZA CON LA IP QUE TE DIO EL MONITOR SERIE DE ARDUINO
ESP32_IP = "localhost o IP" 

def control_led(estado):
    """
    Envía una petición HTTP GET a la ESP32-CAM para controlar el LED.
    estado: 'on' para encender, 'off' para apagar.
    """
    try:
        if estado == "on":
            url = f"http://{ESP32_IP}/led_on"
        elif estado == "off":
            url = f"http://{ESP32_IP}/led_off"
        else:
            print("Estado inválido. Usa 'on' u 'off'.")
            return

        print(f"Enviando petición a: {url}")
        
        # Un timeout corto (2 segundos) para no bloquear el programa si la cámara no responde
        response = requests.get(url, timeout=2) 
        
        if response.status_code == 200:
            print(f"Respuesta de la cámara: {response.text}")
        else:
            print(f"Error HTTP: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión: No se pudo comunicar con la IP {ESP32_IP}.")
        print(f"Detalle del error: {e}")

# --- Secuencia de Prueba ---
if __name__ == "__main__":
    print("Iniciando prueba del LED Flash...")
    
    # Encender
    control_led("on")
    time.sleep(3) # Mantener encendido por 3 segundos
    
    # Apagar
    control_led("off")
    time.sleep(1)
    
    # Parpadear un par de veces rápido
    print("Probando parpadeo rápido...")
    for _ in range(3):
        control_led("on")
        time.sleep(0.5)
        control_led("off")
        time.sleep(0.5)
        
    print("Prueba finalizada.")