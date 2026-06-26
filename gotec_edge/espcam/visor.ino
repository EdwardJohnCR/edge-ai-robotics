#include "esp_camera.h"
#include <WiFi.h>

const char* ssid = "TU_RED_WIFI";
const char* password = "TU_PASSWORD";

// --- CONFIGURACIÓN DE IP FIJA ---
IPAddress local_IP(192, 168, 0, 50);
IPAddress gateway(192, 168, 0, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8); 

#define FLASH_LED_PIN 4

// Pines cámara AI-Thinker
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

// CREAMOS DOS SERVIDORES EN PUERTOS DISTINTOS
WiFiServer serverVideo(80); 
WiFiServer serverCmd(81);   

// --- TAREA INDEPENDIENTE PARA EL LED (Se ejecuta en el Núcleo 0) ---
void tareaControlLED(void * pvParameters) {
  serverCmd.begin();
  for(;;) {// Bucle infinito de la tarea 
    WiFiClient client = serverCmd.available();
    if (client) {
      String request = "";
      while (client.connected()) {
        if (client.available()) {
          char c = client.read();
          request += c;
          if (c == '\n') {
             // Control Digital Puro (Cero ruido armónico)
             if (request.indexOf("GET /led_on") >= 0) {
                digitalWrite(FLASH_LED_PIN, HIGH); 
             } 
             else if (request.indexOf("GET /led_off") >= 0) {
                digitalWrite(FLASH_LED_PIN, LOW);
             }
             else if (request.indexOf("GET /ping") >= 0) {
                // Endpoint para la gráfica de latencia
             }
             
             client.println("HTTP/1.1 200 OK\r\n\r\nOK");
             break;
          }
        }
      }
      client.stop();
    }
    // Pequeña pausa para no saturar el núcleo
    vTaskDelay(10 / portTICK_PERIOD_MS); 
  }
}

void setup() {
  Serial.begin(115200);
  
  // Configuración digital clásica para el LED
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW); 

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM; config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  esp_camera_init(&config);
  WiFi.config(local_IP, gateway, subnet, primaryDNS);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  
    // INICIAMOS LA TAREA DEL LED EN EL NÚCLEO 0
  xTaskCreatePinnedToCore(tareaControlLED, "ControlLED", 4096, NULL, 1, NULL, 0);
  serverVideo.begin();
}

// --- TAREA DE VIDEO (Se ejecuta en el Núcleo 1 por defecto) ---
void loop() {
  WiFiClient client = serverVideo.available();
  if (client) {
    String currentLine = "";
    while (client.connected()) {
      if (client.available()) {
        char c = client.read();
        if (c == '\n') {
          if (currentLine.length() == 0) {
            client.println("HTTP/1.1 200 OK");
            client.println("Content-Type: multipart/x-mixed-replace; boundary=frame\r\n");
            
            while (client.connected()) { 
              camera_fb_t * fb = esp_camera_fb_get();
              if (!fb) continue;
              client.print("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ");
              client.print(fb->len);
              client.print("\r\n\r\n");
              client.write(fb->buf, fb->len);
              client.print("\r\n");
              esp_camera_fb_return(fb);
            }
            break;
          } else { currentLine = ""; }
        } else if (c != '\r') { currentLine += c; }
      }
    }
    client.stop();
  }
}