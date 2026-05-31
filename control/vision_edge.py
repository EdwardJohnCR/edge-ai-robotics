import cv2
import numpy as np
import requests
import time

ESP32_IP = "192.168.0.50"
STREAM_URL = f"http://{ESP32_IP}/"

# Variables de estado
led_encendido = False
UMBRAL_OSCURIDAD = 60

def controlar_led(estado_deseado):
    global led_encendido
    if estado_deseado == led_encendido:
        return 
    
    try:
        if estado_deseado:
            # NOTA EL :81 PARA APUNTAR AL NÚCLEO QUE CONTROLA EL LED
            requests.get(f"http://{ESP32_IP}:81/led_on", timeout=2)
            print("IA: Luz ambiental baja. Encendiendo iluminación.")
        else:
            requests.get(f"http://{ESP32_IP}:81/led_off", timeout=2)
            print("IA: Luz ambiental óptima. Apagando iluminación.")
        led_encendido = estado_deseado
    except Exception as e:
        print(f"Error controlando LED: {e}")

print("Conectando al stream de la planta...")
cap = cv2.VideoCapture(STREAM_URL)

if not cap.isOpened():
    print("Error: No se puede abrir el stream de video.")
    exit()

print("Stream conectado. Iniciando supervisión autónoma (Modo consola)...")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Fallo al capturar el frame.")
        break

    # 1. AUTONOMÍA DE ILUMINACIÓN
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brillo_promedio = np.mean(gris)

    if brillo_promedio < UMBRAL_OSCURIDAD:
        controlar_led(True)
    elif brillo_promedio > (UMBRAL_OSCURIDAD + 20): 
        controlar_led(False)

    # 2. VISIÓN ARTIFICIAL (Lógica)
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
            break # Si encuentra al menos una, rompe el ciclo para no procesar de más
            
    if pieza_detectada:
        print(f"[{time.strftime('%H:%M:%S')}] ¡Pieza azul detectada en la zona!")
        # Aquí enviaríamos la señal al Arduino

    # COMENTADO PARA EVITAR CRASH EN SSH:
    # cv2.imshow("Supervision de Planta IA", frame)
    # if cv2.waitKey(1) & 0xFF == ord('q'):
    #     break

cap.release()
# cv2.destroyAllWindows()
controlar_led(False)