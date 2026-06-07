from flask import Flask, render_template, Response, request, jsonify
import cv2
import numpy as np
import requests
import time

app = Flask(__name__)

# --- CONFIGURACIÓN DE RED ---
ESP32_IP = "192.168.0.50"
STREAM_URL = f"http://{ESP32_IP}:80/"

# --- VARIABLES GLOBALES DEL SISTEMA ---
sistema_estado = {
    "led_encendido": False,
    "modo_auto": True,
    "umbral_encender": 50,
    "umbral_apagar": 180,
    "brillo_actual": 0,
    "pieza_detectada": False,
    "estado_conexion": "Conectando..."
}
ultimo_cambio_luz = 0

def controlar_led_hardware(estado_deseado):
    """Envía la orden HTTP a la ESP32-CAM por el puerto 81"""
    global ultimo_cambio_luz
    if estado_deseado == sistema_estado["led_encendido"]:
        return
    try:
        if estado_deseado:
            requests.get(f"http://{ESP32_IP}:81/led_on", timeout=1.5)
        else:
            requests.get(f"http://{ESP32_IP}:81/led_off", timeout=1.5)
        sistema_estado["led_encendido"] = estado_deseado
        ultimo_cambio_luz = time.time()
    except Exception as e:
        print(f"Error actuador LED: {e}")

# --- RUTAS WEB (ENDPOINTS) ---

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/status')
def status():
    """La página web llama aquí cada segundo para actualizar sus textos"""
    return jsonify(sistema_estado)

@app.route('/api/control', methods=['POST'])
def control():
    """Recibe órdenes de botones y deslizadores desde la web"""
    datos = request.json
    
    if 'modo_auto' in datos:
        sistema_estado["modo_auto"] = datos['modo_auto']
    
    if 'forzar_led' in datos and not sistema_estado["modo_auto"]:
        controlar_led_hardware(datos['forzar_led'])
        
    if 'umbral_encender' in datos:
        sistema_estado["umbral_encender"] = int(datos['umbral_encender'])
        
    if 'umbral_apagar' in datos:
        sistema_estado["umbral_apagar"] = int(datos['umbral_apagar'])

    return jsonify({"status": "ok"})

# --- MOTOR DE VISIÓN E INTELIGENCIA ---

def generar_video():
    """Captura, procesa IA y transmite video a la web"""
    cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            sistema_estado["estado_conexion"] = "Error de Señal"
            # Imagen de error si la cámara falla
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Pérdida de Señal del Sensor", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG) # Intenta reconectar
            time.sleep(1)
        else:
            sistema_estado["estado_conexion"] = "En línea"
            
            # 1. ANÁLISIS DE LUZ
            gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brillo = int(np.mean(gris))
            sistema_estado["brillo_actual"] = brillo
            
            if sistema_estado["modo_auto"]:
                if (time.time() - ultimo_cambio_luz) > 2.0: # Cooldown
                    if brillo < sistema_estado["umbral_encender"] and not sistema_estado["led_encendido"]:
                        controlar_led_hardware(True)
                    elif brillo > sistema_estado["umbral_apagar"] and sistema_estado["led_encendido"]:
                        controlar_led_hardware(False)
            
            # 2. VISIÓN ARTIFICIAL (Pieza Azul)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            azul_bajo = np.array([100, 150, 50])
            azul_alto = np.array([140, 255, 255])
            mascara = cv2.inRange(hsv, azul_bajo, azul_alto)
            contornos, _ = cv2.findContours(mascara, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            sistema_estado["pieza_detectada"] = False
            for contorno in contornos:
                if cv2.contourArea(contorno) > 1000:
                    sistema_estado["pieza_detectada"] = True
                    x, y, w, h = cv2.boundingRect(contorno)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    cv2.putText(frame, "OBJETO DETECTADO", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    break

            # 3. OVERLAY GRÁFICO PARA EL VIDEO
            modo_texto = "AUTO" if sistema_estado["modo_auto"] else "MANUAL"
            color_modo = (0, 255, 0) if sistema_estado["modo_auto"] else (0, 165, 255)
            cv2.putText(frame, f"Modo: {modo_texto}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_modo, 2)
            cv2.putText(frame, f"Brillo: {brillo}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Codificar a JPEG para enviarlo a la web
        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generar_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # host='0.0.0.0' permite acceso desde cualquier dispositivo en tu red
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)