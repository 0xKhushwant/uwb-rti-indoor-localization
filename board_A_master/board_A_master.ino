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

const char* NODE_NAME = "A";
char tag_addr[] = "7D:00:22:EA:82:60:3B:A1";

struct LinkSample {
  uint16_t shortAddr = 0;
  float range = 0;
  float rx = 0;
  unsigned long lastSeen = 0;
  bool valid = false;
};

LinkSample samples[8];
unsigned long lastPush = 0;
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

int findSlot(uint16_t addr) {
  for (int i = 0; i < 8; i++) {
    if (samples[i].valid && samples[i].shortAddr == addr) return i;
  }
  for (int i = 0; i < 8; i++) {
    if (!samples[i].valid) return i;
  }
  return 0;
}

void newRange() {
  DW1000Device* device = DW1000Ranging.getDistantDevice();
  if (!device) return;

  float range = device->getRange();
  float rx = device->getRXPower();

  // Filter impossible values
  if (range <= 0 || range > 20) return;

  uint16_t addr = device->getShortAddress();
  int idx = findSlot(addr);

  samples[idx].shortAddr = addr;
  samples[idx].range = range;
  samples[idx].rx = rx;
  samples[idx].lastSeen = millis();
  samples[idx].valid = true;

  Serial.print("FROM: ");
  Serial.print(addr, HEX);
  Serial.print(" | Range: ");
  Serial.print(range, 2);
  Serial.print(" m | RX: ");
  Serial.println(rx, 2);
}

void newDevice(DW1000Device *device) {
  Serial.print("CONNECTED TO: ");
  Serial.println(device->getShortAddress(), HEX);
}

void inactiveDevice(DW1000Device *device) {
  Serial.print("DISCONNECTED: ");
  Serial.println(device->getShortAddress(), HEX);
}

void pushSamples() {
  for (int i = 0; i < 8; i++) {
    if (!samples[i].valid) continue;
    if (millis() - samples[i].lastSeen > 5000) continue;

    String peerHex = String(samples[i].shortAddr, HEX);
    peerHex.toUpperCase();

    String payload = "{";
    payload += "\"node\":\"" + String(NODE_NAME) + "\",";
    payload += "\"type\":\"ranging\",";
    payload += "\"peer\":\"" + peerHex + "\",";
    payload += "\"range\":" + String(samples[i].range, 2) + ",";
    payload += "\"rx\":" + String(samples[i].rx, 2) + ",";
    payload += "\"millis\":" + String(millis()) + ",";
    payload += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
    payload += "\"wifi_rssi\":" + String(WiFi.RSSI());
    payload += "}";

    postJson(payload);
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("MASTER NODE STARTED");

  connectWiFi();

  SPI.begin(18, 19, 23);
  DW1000Ranging.initCommunication(PIN_RST, PIN_SS, PIN_IRQ);

  DW1000Ranging.attachNewRange(newRange);
  DW1000Ranging.attachNewDevice(newDevice);
  DW1000Ranging.attachInactiveDevice(inactiveDevice);

  DW1000Ranging.startAsTag(tag_addr, DW1000.MODE_LONGDATA_RANGE_ACCURACY);

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

  if (millis() - lastPush > 1000) {
    pushSamples();
    lastPush = millis();
  }
}