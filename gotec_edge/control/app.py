from flask import Flask, render_template, Response, request, jsonify
import cv2
import numpy as np
import requests
import time

app = Flask(__name__)

ESP32_IP = "192.168.0.50"
STREAM_URL = f"http://{ESP32_IP}:80/"

sistema_estado = {
    "brillo_led": 0,          # 0 a 255
    "pieza_detectada": False,
    "latencia_ms": 0,         # Para la gráfica
    "estado_conexion": "Conectando..."
}

def medir_latencia():
    """Hace un ping HTTP a la cámara para medir el tiempo de respuesta real"""
    inicio = time.time()
    try:
        # Hacemos petición al nuevo endpoint /ping
        requests.get(f"http://{ESP32_IP}:81/ping", timeout=0.5)
        return int((time.time() - inicio) * 1000)
    except:
        return -1 # -1 significa error o desconexión

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/status')
def status():
    # Medimos la latencia en cada solicitud del dashboard
    lat = medir_latencia()
    sistema_estado["latencia_ms"] = lat
    sistema_estado["estado_conexion"] = "En línea" if lat >= 0 else "Desconectado"
    return jsonify(sistema_estado)

@app.route('/api/control', methods=['POST'])
def control():
    datos = request.json
    
    # Si recibimos orden ON/OFF rápida
    if 'forzar_led' in datos:
        estado = datos['forzar_led']
        valor_pwm = 255 if estado else 0
        try:
            requests.get(f"http://{ESP32_IP}:81/led_pwm?val={valor_pwm}", timeout=1.0)
            sistema_estado["brillo_led"] = valor_pwm
        except:
            pass
            
    # Si recibimos el deslizador de brillo
    if 'brillo_pwm' in datos:
        valor_pwm = int(datos['brillo_pwm'])
        try:
            requests.get(f"http://{ESP32_IP}:81/led_pwm?val={valor_pwm}", timeout=1.0)
            sistema_estado["brillo_led"] = valor_pwm
        except:
            pass

    return jsonify({"status": "ok"})

def generar_video():
    cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Perdida de Senal", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)
            time.sleep(1)
        else:
            # VISIÓN ARTIFICIAL
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
                    cv2.putText(frame, "PIEZA EN POSICION", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    break

            # Textos en pantalla (solo modo manual)
            cv2.putText(frame, "Modo: MANUAL (PWM)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generar_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)