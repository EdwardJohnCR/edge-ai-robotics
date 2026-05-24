import cv2
import numpy as np
import requests
import time

ESP32_IP = "192.168.1.50"
STREAM_URL = f"http://{ESP32_IP}/"

# Variables de estado
led_encendido = False
UMBRAL_OSCURIDAD = 60  # De 0 (negro) a 255 (blanco). Ajusta según el salón.

def controlar_led(estado_deseado):
    global led_encendido
    if estado_deseado == led_encendido:
        return # No hacer nada si ya está en el estado correcto (evita saturar la red)
    
    try:
        if estado_deseado:
            requests.get(f"http://{ESP32_IP}/led_on", timeout=1)
            print("IA: Luz ambiental baja. Encendiendo iluminación de la celda.")
        else:
            requests.get(f"http://{ESP32_IP}/led_off", timeout=1)
            print("IA: Luz ambiental óptima. Apagando iluminación.")
        led_encendido = estado_deseado
    except Exception as e:
        print(f"Error controlando LED: {e}")

print("Conectando al stream de la planta...")
cap = cv2.VideoCapture(STREAM_URL)

if not cap.isOpened():
    print("Error: No se puede abrir el stream de video.")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Fallo al capturar el frame.")
        break

    # 1. AUTONOMÍA DE ILUMINACIÓN
    # Convertimos a escala de grises y calculamos el promedio de píxeles
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brillo_promedio = np.mean(gris)

    if brillo_promedio < UMBRAL_OSCURIDAD:
        controlar_led(True)
    elif brillo_promedio > (UMBRAL_OSCURIDAD + 20): # +20 evita que parpadee si está justo en el límite (Histéresis)
        controlar_led(False)

    # 2. VISIÓN ARTIFICIAL (Detección de objeto azul)
    # Convertimos de BGR (formato OpenCV) a HSV (ideal para aislar colores)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Rango para el color AZUL. (Puedes cambiarlo al color de tus piezas)
    azul_bajo = np.array([100, 150, 50])
    azul_alto = np.array([140, 255, 255])
    
    # Crear una máscara que solo deje pasar los píxeles azules
    mascara = cv2.inRange(hsv, azul_bajo, azul_alto)
    
    # Encontrar contornos (los bordes del objeto)
    contornos, _ = cv2.findContours(mascara, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area > 1000:  # Ignorar ruido pequeño (ajustar según el tamaño del objeto)
            x, y, w, h = cv2.boundingRect(contorno)
            
            # Dibujar rectángulo verde alrededor del objeto
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Poner texto identificando la "Pieza"
            cv2.putText(frame, "Pieza Detectada", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # AQUÍ IRÍA LA LÓGICA DE COMUNICACIÓN SERIAL HACIA EL ARDUINO
            # ej. enviar_comando_serial("AGARRAR_PIEZA")

    # Mostrar métricas en la pantalla para la audiencia
    cv2.putText(frame, f"Brillo: {int(brillo_promedio)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, f"LED: {'ON' if led_encendido else 'OFF'}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Mostrar la ventana
    cv2.imshow("Supervision de Planta IA", frame)

    # Presionar 'q' para salir
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
controlar_led(False) # Asegurar que el LED quede apagado al salir