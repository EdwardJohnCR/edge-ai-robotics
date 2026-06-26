#include <Servo.h>

Servo servoBase;
Servo servoHombro;
Servo servoCodo;
Servo servoPinza;

const int PIN_BASE = 9;
const int PIN_HOMBRO = 10;
const int PIN_CODO = 11;
const int PIN_PINZA = 12;

// Posición inicial de reposo 1 (Tus coordenadas seguras)
int posActual[4] = {100, 160, 90, 90}; 

void setup() {
  Serial.begin(115200);
  
  servoBase.attach(PIN_BASE);
  servoHombro.attach(PIN_HOMBRO);
  servoCodo.attach(PIN_CODO);
  servoPinza.attach(PIN_PINZA);
  
  // Mover a la posición inicial desde el arranque
  servoBase.write(posActual[0]);
  servoHombro.write(posActual[1]);
  servoCodo.write(posActual[2]);
  servoPinza.write(posActual[3]);
  
  Serial.println("ARDUINO_LISTO");
}

void loop() {
  if (Serial.available() > 0) {
    String datos = Serial.readStringUntil('\n');
    
    int ind1 = datos.indexOf(',');
    int ind2 = datos.indexOf(',', ind1 + 1);
    int ind3 = datos.indexOf(',', ind2 + 1);
    
    if (ind1 > 0 && ind2 > 0 && ind3 > 0) {
      int t_base = datos.substring(0, ind1).toInt();
      int t_hombro = datos.substring(ind1 + 1, ind2).toInt();
      int t_codo = datos.substring(ind2 + 1, ind3).toInt();
      int t_pinza = datos.substring(ind3 + 1).toInt();
      
      // --- LÍMITES DE SEGURIDAD (Software Limit Switches) ---
      if (t_base < 0) t_base = 0;       if (t_base > 180) t_base = 180;
      if (t_hombro < 110) t_hombro = 110; if (t_hombro > 180) t_hombro = 180;
      if (t_codo < 20) t_codo = 20;       if (t_codo > 160) t_codo = 160;
      if (t_pinza < 20) t_pinza = 20;     if (t_pinza > 90) t_pinza = 90; 
      
      // Ejecutar el movimiento coordinado
      // El '20' final es el retraso en ms por paso. Auméntalo (ej: 30 o 40) si quieres que se mueva más lento.
      moverBrazoCoordinado(t_base, t_hombro, t_codo, t_pinza, 20);
    }
  }
}

// --- FUNCIÓN INDUSTRIAL: Interpolación Lineal Sincronizada ---
void moverBrazoCoordinado(int b, int h, int c, int p, int velocidad_ms) {
  int destino[4] = {b, h, c, p};
  int inicio[4] = {posActual[0], posActual[1], posActual[2], posActual[3]};
  
  // 1. Encontrar cuál servo tiene que recorrer la mayor distancia
  int maxPasos = 0;
  for (int i = 0; i < 4; i++) {
    int recorrido = abs(destino[i] - inicio[i]);
    if (recorrido > maxPasos) {
      maxPasos = recorrido;
    }
  }

  // Si ya estamos en esa posición, no hacemos nada
  if (maxPasos == 0) return;

  // 2. Mover todos los motores proporcionalmente para que terminen al mismo tiempo
  for (int paso = 1; paso <= maxPasos; paso++) {
    for (int i = 0; i < 4; i++) {
      // Fórmula matemática de interpolación
      posActual[i] = inicio[i] + ((destino[i] - inicio[i]) * paso) / maxPasos;
    }
    
    // Aplicar las nuevas posiciones parciales
    servoBase.write(posActual[0]);
    servoHombro.write(posActual[1]);
    servoCodo.write(posActual[2]);
    servoPinza.write(posActual[3]);
    
    // Esperar un instante antes de dar el siguiente micro-paso
    delay(velocidad_ms); 
  }
}