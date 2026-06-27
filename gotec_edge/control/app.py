from flask import Flask, render_template, Response, request, jsonify
import cv2
import numpy as np
import requests
import time
import serial
import threading
import glob # Librería para buscar archivos y puertos en Linux

app = Flask(__name__)

# --- CONFIGURACIÓN DE RED ---
ESP32_IP = "192.168.0.50"
STREAM_URL = f"http://{ESP32_IP}:80/"

# --- VARIABLES GLOBALES DEL SISTEMA ---
sistema_estado = {
    "led_encendido": False,
    "brillo_led": 0,          
    "pieza_detectada": False,
    "color_detectado": "Ninguno",
    "latencia_ms": 0,
    "estado_conexion": "Conectando...",
    "arduino_conectado": False,
    "puerto_arduino": "Buscando...",
    "robot_moviendose": False # Centralizamos el estado del movimiento aquí
}

# --- AUTO-DESCUBRIMIENTO DEL ARDUINO ---
arduino = None
puertos_posibles = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')

for puerto in puertos_posibles:
    try:
        arduino = serial.Serial(puerto, 115200, timeout=1)
        sistema_estado["arduino_conectado"] = True
        sistema_estado["puerto_arduino"] = puerto
        print(f"¡Éxito! Arduino encontrado y conectado en: {puerto}")
        break # Si conecta, salimos del ciclo de búsqueda
    except Exception as e:
        print(f"Fallo al intentar puerto {puerto}: {e}")

if not arduino:
    sistema_estado["puerto_arduino"] = "No detectado"
    print("CRÍTICO: No se detectó ningún Arduino conectado a los puertos USB.")

tiempo_ultimo_movimiento = 0

def medir_latencia():
    inicio = time.time()
    try:
        requests.get(f"http://{ESP32_IP}:81/ping", timeout=0.5)
        return int((time.time() - inicio) * 1000)
    except:
        return -1

# --- RUTAS WEB ---
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/status')
def status():
    lat = medir_latencia()
    sistema_estado["latencia_ms"] = lat
    sistema_estado["estado_conexion"] = "En línea" if lat >= 0 else "Desconectado"
    return jsonify(sistema_estado)

@app.route('/api/control', methods=['POST'])
def control():
    datos = request.json
    if 'forzar_led' in datos:
        estado = datos['forzar_led']
        try:
            if estado: requests.get(f"http://{ESP32_IP}:81/led_on", timeout=1.0)
            else: requests.get(f"http://{ESP32_IP}:81/led_off", timeout=1.0)
            sistema_estado["led_encendido"] = estado
            sistema_estado["brillo_led"] = 255 if estado else 0
        except: pass
    return jsonify({"status": "ok"})

# --- MOTOR DE VISIÓN Y CINEMÁTICA ---
def generar_video():
    global tiempo_ultimo_movimiento
    
    cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Perdida de Senal - Reconectando", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)
            time.sleep(1)
        else:
          # Convertimos a HSV para segmentación de color
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # 1. RANGO DE COLOR HSV (Exclusivo para el Azul)
            azul_bajo = np.array([100, 150, 50])
            azul_alto = np.array([140, 255, 255])
            mascara_azul = cv2.inRange(hsv, azul_bajo, azul_alto)
            
            # Solo buscamos contornos en la máscara azul
            contornos, _ = cv2.findContours(mascara_azul, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            pieza_encontrada = False
            color_encontrado = "Ninguno"
            cx, cy = 0, 0
            
            for contorno in contornos:
                if cv2.contourArea(contorno) > 1200: 
                    pieza_encontrada = True
                    x, y, w, h = cv2.boundingRect(contorno)
                    cx = x + (w // 2)
                    cy = y + (h // 2)
                    
                    # Asignamos directamente el color azul
                    color_encontrado = "Azul"
                    color_bgr = (255, 0, 0) # Color para dibujar en pantalla
                    
                    cv2.rectangle(frame, (x, y), (x+w, y+h), color_bgr, 2)
                    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1) 
                    cv2.putText(frame, f"PIEZA {color_encontrado.upper()}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_bgr, 2)
                    break

            sistema_estado["pieza_detectada"] = pieza_encontrada
            sistema_estado["color_detectado"] = color_encontrado

            # 2. CINEMÁTICA Y TRAYECTORIAS OPTIMIZADAS
            if pieza_encontrada and not sistema_estado["robot_moviendose"] and arduino:
                sistema_estado["robot_moviendose"] = True
                tiempo_ultimo_movimiento = time.time()
                
                # Mapeo de la Base (Eje X) y Codo (Eje Y/Profundidad)
                angulo_base = int(np.interp(cx, [0, 640], [160, 30]))
                angulo_codo = int(np.interp(cy, [0, 480], [80, 30]))
                
                # --- ASIGNACIÓN DE ZONA DE DESCARGA ---
                # Lo mandamos a la derecha (160°). 
                # Si tu brazo físico gira al revés, simplemente cambia este 160 por un 20.
                base_descarga = 160 
                
                pinza_abierta = 35
                pinza_cerrada = 130
                
                # --- RUTINA OPTIMIZADA (Brazo extendido y seguro) ---
                rutina = [
                    f"{angulo_base},140,{angulo_codo},{pinza_abierta}\n", # Hover: Se posiciona encima
                    f"{angulo_base},140,{angulo_codo},{pinza_abierta}\n", # Baja: Toca la mesa
                    f"{angulo_base},140,{angulo_codo},{pinza_cerrada}\n", # Agarra: Cierra pinza
                    
                    # SUBE: Se levanta manteniendo el brazo proyectado hacia adelante (125, 110)
                    f"{angulo_base},125,110,{pinza_cerrada}\n", 
                    
                    # GIRA: Traslado hacia la zona de descarga
                    f"{base_descarga},125,110,{pinza_cerrada}\n",
                    
                    f"{base_descarga},140,50,{pinza_cerrada}\n",          # Baja en la zona de descarga
                    f"{base_descarga},140,50,{pinza_abierta}\n",          # Suelta el objeto
                    f"100,140,90,90\n"                                    # Vuelve a Reposo Central
                ]
                
                def ejecutar_rutina():
                    for paso in rutina:
                        arduino.write(paso.encode())
                        time.sleep(2.0) 
                
                threading.Thread(target=ejecutar_rutina).start()
            
            # El bloqueo dura 16 segundos
            if sistema_estado["robot_moviendose"] and (time.time() - tiempo_ultimo_movimiento) > 16.0:
                sistema_estado["robot_moviendose"] = False

            # TEXTOS EN PANTALLA
            cv2.putText(frame, f"Target: {color_encontrado}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Imprimir estado de Arduino en el video
            if arduino:
                cv2.putText(frame, f"PLC: OK ({sistema_estado['puerto_arduino']})", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "PLC: DESCONECTADO", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            if sistema_estado["robot_moviendose"]:
                cv2.putText(frame, "EJECUTANDO CLASIFICACION...", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generar_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)