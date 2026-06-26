#include <Servo.h>

Servo servoBase;   // Pin 9
Servo servoHombro; // Pin 7
Servo servoCodo;   // Pin 6
Servo servoPinza;  // Pin 5

// Posiciones iniciales de seguridad (90 grados suele ser el centro)
int posB = 90; // base home
int posH = 90; // hombro home
int posC = 90; // codo home
int posP = 90; // piensa home

// AJUSTAR POSICIÓN DEL BRAZO EN EL PONTO DE HOME Y 90° DEL LOS SERVOS

void setup() {
  // Asegúrate de que el Monitor Serie esté en 115200 baudios
  Serial.begin(115200); 
  
  servoBase.attach(6);
  servoHombro.attach(5);
  servoCodo.attach(9);
  servoPinza.attach(7);

  // Ir a la posición de inicio
  servoBase.write(posB);
  servoHombro.write(posH);
  servoCodo.write(posC);
  servoPinza.write(posP);

  Serial.println("--- MODO CALIBRACION INICIADO ---");
  Serial.println("Instrucciones: Escribe la inicial del servo seguido del angulo (0 a 180).");
  Serial.println("Ejemplos: B45 (Base a 45), H120 (Hombro a 120), C90 (Codo a 90), P10 (Pinza a 10)");
  Serial.println("---------------------------------");
}

void loop() {
  // Verificamos si hay datos entrantes en el puerto Serial
  if (Serial.available() > 0) {
    
    // Leemos la primera letra para saber qué servo mover
    char servoTarget = Serial.read();
    
    // Leemos el número que le sigue
    int angulo = Serial.parseInt();

    // Solo ejecutamos si el ángulo es válido para un servo (0 a 180)
    if (angulo >= 0 && angulo <= 180) {
      
      // Convertimos la letra a mayúscula internamente por si la escribes en minúscula
      servoTarget = toupper(servoTarget);

      // Asignamos el ángulo al servo correspondiente
      switch (servoTarget) {
        case 'B':
          posB = angulo;
          servoBase.write(posB);
          break;
        case 'H':
          posH = angulo;
          servoHombro.write(posH);
          break;
        case 'C':
          posC = angulo;
          servoCodo.write(posC);
          break;
        case 'P':
          posP = angulo;
          servoPinza.write(posP);
          break;
        default:
          // Si escribes otra letra, limpia el buffer y no hace nada
          while(Serial.available() > 0) Serial.read();
          return; 
      }

      // Imprimimos el estado actual con el formato exacto que usaremos después
      Serial.print("Coordenada actual: <");
      Serial.print(posB); Serial.print(",");
      Serial.print(posH); Serial.print(",");
      Serial.print(posC); Serial.print(",");
      Serial.print(posP); Serial.println(">");
    }
  }
}