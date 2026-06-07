import cv2
import numpy as np
import requests
import time

ESP32_IP = "192.168.0.50"
# Añadimos explícitamente el puerto 80 para mayor estabilidad en la petición
STREAM_URL = f"http://{ESP32_IP}:80/" 

# Variables de estado y calibración
led_encendido = False
UMBRAL_ENCENDER = 50
UMBRAL_APAGAR = 180
TIEMPO_COOLDOWN = 2.0
ultimo_cambio_luz = 0

def controlar_led(estado_deseado):
    global led_encendido, ultimo_cambio_luz
    if estado_deseado == led_encendido:
        return 
    
    try:
        if estado_deseado:
            requests.get(f"http://{ESP32_IP}:81/led_on", timeout=2)
            print(f"[{time.strftime('%H:%M:%S')}] IA: Luz ambiental baja. Encendiendo iluminación...")
        else:
            requests.get(f"http://{ESP32_IP}:81/led_off", timeout=2)
            print(f"[{time.strftime('%H:%M:%S')}] IA: Luz ambiental óptima. Apagando iluminación...")
            
        led_encendido = estado_deseado
        ultimo_cambio_luz = time.time()
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error de comunicación con actuador LED: {e}")

# --- FUNCIÓN WATCHDOG (Reconexión Autónoma) ---
def conectar_camara():
    print(f"[{time.strftime('%H:%M:%S')}] Conectando al nodo sensor (ESP32-CAM)...")
    # cv2.CAP_FFMPEG fuerza a usar un motor más estable que GStreamer
    captura = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)
    
    # Reducimos el tamaño del buffer para tener latencia cero en la respuesta del brazo
    captura.set(cv2.CAP_PROP_BUFFERSIZE, 2) 
    return captura

# Iniciamos la primera conexión
cap = conectar_camara()

print("Agente Supervisor IA iniciado. Monitoreo en curso...")

while True:
    ret, frame = cap.read()
    
    # Si la cámara falla o el Wi-Fi parpadea, entra el Watchdog
    if not ret:
        print(f"[{time.strftime('%H:%M:%S')}] ADVERTENCIA: Pérdida de señal del sensor. Intentando reconectar en 3s...")
        cap.release()
        time.sleep(3) # Espera a que el router estabilice la red
        cap = conectar_camara() # Intenta conectarse de nuevo
        continue # Vuelve al inicio del bucle sin abortar el programa

    tiempo_actual = time.time()

    # 1. AUTONOMÍA DE ILUMINACIÓN (Histéresis)
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brillo_promedio = np.mean(gris)
    
    if (tiempo_actual - ultimo_cambio_luz) > TIEMPO_COOLDOWN:
        if brillo_promedio < UMBRAL_ENCENDER and not led_encendido:
            controlar_led(True)
        elif brillo_promedio > UMBRAL_APAGAR and led_encendido:
            controlar_led(False)

    # 2. VISIÓN ARTIFICIAL (Clasificación)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    azul_bajo = np.array([100, 150, 50])
    azul_alto = np.array([140, 255, 255])
    mascara = cv2.inRange(hsv, azul_bajo, azul_alto)
    contornos, _ = cv2.findContours(mascara, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    pieza_detectada = False
    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area > 1000:  
            pieza_detectada = True
            break
            
    if pieza_detectada:
        print(f"[{time.strftime('%H:%M:%S')}] ¡Pieza detectada en la zona de trabajo!")

    # Impresión de estado (1 vez por segundo)
    if int(tiempo_actual * 10) % 10 == 0: 
        print(f"Estado Sensor -> Brillo: {int(brillo_promedio):03d} | LED: {'ON ' if led_encendido else 'OFF'}", end='\r')

# Liberación de recursos (solo si sales del programa manualmente)
cap.release()
controlar_led(False)