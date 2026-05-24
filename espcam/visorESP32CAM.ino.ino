#include "esp_camera.h"
#include <WiFi.h>

// Reemplaza con los datos de tu red Wi-Fi
const char* ssid = "Alquiler";
const char* password = "ALQUILER001";

// Pin del Flash LED integrado
#define FLASH_LED_PIN 4

// Pines para el modelo de placa AI-Thinker
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WiFiServer server(80);

void setup() {
  Serial.begin(115200);

  // Inicializar el pin del LED y asegurar que inicie apagado
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Resolución VGA (640x480)
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Error iniciando la cámara: 0x%x", err);
    return;
  }

  Serial.print("Conectando a Wi-Fi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("¡Wi-Fi conectado!");
  Serial.print("Servidor listo en IP: ");
  Serial.println(WiFi.localIP());

  server.begin();
}

void loop() {
  WiFiClient client = server.available();
  if (client) {
    String currentLine = "";
    String request = ""; // Variable para guardar la petición HTTP completa
    
    while (client.connected()) {
      if (client.available()) {
        char c = client.read();
        request += c; // Ir armando el request
        
        if (c == '\n') {
          if (currentLine.length() == 0) {
            
            // 1. EVALUAR SI SE PIDIÓ ENCENDER EL LED
            if (request.indexOf("GET /led_on") >= 0) {
              digitalWrite(FLASH_LED_PIN, HIGH);
              client.println("HTTP/1.1 200 OK");
              client.println("Content-type:text/plain");
              client.println();
              client.println("LED ENCENDIDO");
              break;
            } 
            
            // 2. EVALUAR SI SE PIDIÓ APAGAR EL LED
            else if (request.indexOf("GET /led_off") >= 0) {
              digitalWrite(FLASH_LED_PIN, LOW);
              client.println("HTTP/1.1 200 OK");
              client.println("Content-type:text/plain");
              client.println();
              client.println("LED APAGADO");
              break;
            }
            
            // 3. SI NO ES NINGUNO DE LOS ANTERIORES, INICIAR STREAM DE VIDEO
            else {
              client.println("HTTP/1.1 200 OK");
              client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
              client.println();

              while (client.connected()) {
                camera_fb_t * fb = esp_camera_fb_get();
                if (!fb) {
                  continue;
                }
                
                client.print("--frame\r\n");
                client.print("Content-Type: image/jpeg\r\n");
                client.print("Content-Length: ");
                client.print(fb->len);
                client.print("\r\n\r\n");
                client.write(fb->buf, fb->len);
                client.print("\r\n");
                
                esp_camera_fb_return(fb);
              }
            }
            break;
          } else {
            currentLine = "";
          }
        } else if (c != '\r') {
          currentLine += c;
        }
      }
    }
    client.stop();
  }
}