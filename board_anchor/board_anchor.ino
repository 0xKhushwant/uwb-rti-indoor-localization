#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include "DW1000Ranging.h"
#include "DW1000.h"

const char* WIFI_SSID = "Devil";      // fill this
const char* WIFI_PASS = "karya123456";      // fill this
const char* SERVER_URL = "http://172.22.244.47:5000/api/ingest";

#define PIN_RST 27
#define PIN_SS  4
#define PIN_IRQ 34

const char* NODE_NAME = "D";
char anchor_addr[] = "7D:00:22:EA:82:60:3B:D1";

unsigned long lastHeartbeat = 0;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("WiFi connected. IP: ");
  Serial.println(WiFi.localIP());
}

void postJson(const String& payload) {
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;
  if (!http.begin(client, SERVER_URL)) return;

  http.addHeader("Content-Type", "application/json");
  http.POST(payload);
  http.end();
}

void sendHeartbeat() {
  String payload = "{";
  payload += "\"node\":\"" + String(NODE_NAME) + "\",";
  payload += "\"type\":\"heartbeat\",";
  payload += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  payload += "\"wifi_rssi\":" + String(WiFi.RSSI());
  payload += "}";
  postJson(payload);
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("ANCHOR STARTED");

  connectWiFi();

  SPI.begin(18, 19, 23);
  DW1000Ranging.initCommunication(PIN_RST, PIN_SS, PIN_IRQ);

  DW1000Ranging.startAsAnchor(anchor_addr, DW1000.MODE_LONGDATA_RANGE_ACCURACY);

  sendHeartbeat();
  lastHeartbeat = millis();
}

void loop() {
  DW1000Ranging.loop();

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (millis() - lastHeartbeat > 10000) {
    sendHeartbeat();
    lastHeartbeat = millis();
  }
}