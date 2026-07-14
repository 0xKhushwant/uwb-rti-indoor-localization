#include <WiFi.h>
#include <WiFiUdp.h>
#include <HTTPClient.h>
#include <SPI.h>
#include "DW1000.h"
#include "DW1000Ranging.h"
#include "common.h"
#include "config.h"
#include "secrets.h"

enum class RadioRole : uint8_t {
  Unknown,
  Tag,
  Anchor,
};

const char LOCAL_NODE = NODE_NAME[0];
const NodeInfo *localInfo = nullptr;
char localUwbAddress[24] = {0};
char serverUrl[96] = SERVER_FALLBACK_URL;
WiFiUDP discoveryUdp;

RadioRole currentRole = RadioRole::Unknown;
uint8_t currentSlot = 255;
uint32_t lastHeartbeatMs = 0;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastDiscoveryAttemptMs = 0;
uint8_t failedPostCount = 0;
RangingSample latestSamples[LINK_COUNT];

// Finds the Flask server after hotspot restarts so the firmware does not need reflashing.
bool discoverServer() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  IPAddress broadcastIp = WiFi.localIP();
  broadcastIp[3] = 255;

  discoveryUdp.begin(0);
  discoveryUdp.beginPacket(broadcastIp, DISCOVERY_PORT);
  discoveryUdp.write(reinterpret_cast<const uint8_t *>(DISCOVERY_REQUEST), strlen(DISCOVERY_REQUEST));
  discoveryUdp.endPacket();

  const uint32_t startedMs = millis();
  while (millis() - startedMs < 350) {
    const int packetSize = discoveryUdp.parsePacket();
    if (packetSize <= 0) {
      delay(10);
      continue;
    }

    char response[96] = {0};
    const int length = discoveryUdp.read(response, sizeof(response) - 1);
    response[length] = '\0';

    if (strncmp(response, DISCOVERY_RESPONSE_PREFIX, strlen(DISCOVERY_RESPONSE_PREFIX)) == 0) {
      strlcpy(serverUrl, response + strlen(DISCOVERY_RESPONSE_PREFIX), sizeof(serverUrl));
      Serial.print(F("Discovered RTI server: "));
      Serial.println(serverUrl);
      return true;
    }
  }

  Serial.print(F("Server discovery failed, using fallback: "));
  Serial.println(serverUrl);
  return false;
}

// Connects to the hotspot without permanently blocking the TDMA/ranging loop.
void maintainWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  strlcpy(serverUrl, SERVER_FALLBACK_URL, sizeof(serverUrl));
  const uint32_t now = millis();
  if (now - lastWifiAttemptMs < WIFI_RETRY_INTERVAL_MS) {
    return;
  }

  lastWifiAttemptMs = now;
  WiFi.disconnect(false);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.println(F("WiFi reconnect requested"));
}

// Sends a JSON payload to the Flask ingest endpoint with a short timeout.
bool postJson(const char *payload) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  WiFiClient client;
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);

  if (!http.begin(client, serverUrl)) {
    return false;
  }

  http.addHeader(F("Content-Type"), F("application/json"));
  const int code = http.POST(reinterpret_cast<uint8_t *>(const_cast<char *>(payload)), strlen(payload));
  http.end();
  const bool ok = code >= 200 && code < 300;
  if (ok) {
    failedPostCount = 0;
  } else if (++failedPostCount >= 3) {
    failedPostCount = 0;
    strlcpy(serverUrl, SERVER_FALLBACK_URL, sizeof(serverUrl));
    discoverServer();
  }
  return ok;
}

// Emits a one-second liveness packet so the server can mark boards online/offline.
void sendHeartbeat() {
  char payload[JSON_BUFFER_SIZE];
  snprintf(payload, sizeof(payload),
           "{\"source\":\"%c\",\"node\":\"%c\",\"type\":\"heartbeat\",\"wifi_rssi\":%ld,"
           "\"timestamp\":%lu,\"online\":true}",
           LOCAL_NODE, LOCAL_NODE, static_cast<long>(WiFi.RSSI()),
           static_cast<unsigned long>(millis()));
  postJson(payload);
}

// Formats and sends one successful ranging event in the RTI six-link schema.
void sendRangingSample(const RangingSample &sample) {
  const char *name = linkName(sample.source, sample.target);
  if (name[0] == '\0') {
    return;
  }

  char payload[JSON_BUFFER_SIZE];
  snprintf(payload, sizeof(payload),
           "{\"source\":\"%c\",\"target\":\"%c\",\"link\":\"%s\",\"range\":%.2f,"
           "\"rx_power\":%.2f,\"fp_power\":%.2f,\"wifi_rssi\":%ld,"
           "\"timestamp\":%lu,\"online\":true}",
           sample.source, sample.target, name, sample.range, sample.rxPower,
           sample.fpPower, static_cast<long>(WiFi.RSSI()),
           static_cast<unsigned long>(sample.timestamp));
  postJson(payload);
}

// Returns true during the center of the slot and false during guard time.
bool slotIsInsideActiveWindow(uint32_t cycleOffsetMs) {
  const uint32_t slotOffset = cycleOffsetMs % TDMA_SLOT_MS;
  return slotOffset >= SLOT_GUARD_MS && slotOffset < (TDMA_SLOT_MS - SLOT_GUARD_MS);
}

// Reconfigures the Makerfabs DW1000Ranging object as tag or anchor.
void setRadioRole(RadioRole role) {
  if (role == currentRole) {
    return;
  }

  currentRole = role;
  if (role == RadioRole::Tag) {
    DW1000Ranging.startAsTag(localUwbAddress, DW1000.MODE_LONGDATA_RANGE_ACCURACY, false);
    Serial.println(F("UWB role: tag initiator"));
  } else {
    DW1000Ranging.startAsAnchor(localUwbAddress, DW1000.MODE_LONGDATA_RANGE_ACCURACY, false);
    Serial.println(F("UWB role: anchor/listener"));
  }
}

// Applies the 1000 ms TDMA schedule: A tags, then B tags, then C tags, then idle/listen.
void maintainTdmaRole() {
  const uint32_t cycleOffset = millis() % TDMA_CYCLE_MS;
  const uint8_t slot = cycleOffset / TDMA_SLOT_MS;
  const char initiator = initiatorForSlot(slot);
  const bool shouldInitiate = initiator == LOCAL_NODE && slotIsInsideActiveWindow(cycleOffset);

  if (slot != currentSlot) {
    currentSlot = slot;
    Serial.printf("TDMA slot %u initiator %c\n", slot, initiator);
  }

  setRadioRole(shouldInitiate ? RadioRole::Tag : RadioRole::Anchor);
}

// Makerfabs callback for each completed DW1000 range measurement.
void onNewRange() {
  DW1000Device *device = DW1000Ranging.getDistantDevice();
  if (device == nullptr) {
    return;
  }

  const NodeInfo *peer = findNodeByShortAddress(device->getShortAddress());
  if (peer == nullptr || !isScheduledTarget(LOCAL_NODE, peer->name)) {
    Serial.printf("Ignored UWB range from short address 0x%X while node %c is active\n",
                  device->getShortAddress(), LOCAL_NODE);
    return;
  }

  const float range = device->getRange();
  if (range < MIN_VALID_RANGE_M || range > MAX_VALID_RANGE_M) {
    return;
  }

  RangingSample sample;
  sample.source = LOCAL_NODE;
  sample.target = peer->name;
  sample.range = range;
  sample.rxPower = device->getRXPower();
  sample.fpPower = device->getFPPower();
  sample.timestamp = millis();
  sample.valid = true;

  Serial.printf("%c-%c range %.2f m RX %.2f FP %.2f\n", sample.source, sample.target,
                sample.range, sample.rxPower, sample.fpPower);
  sendRangingSample(sample);
}

// Makerfabs callback for discovered peer devices.
void onNewDevice(DW1000Device *device) {
  if (device != nullptr) {
    Serial.printf("UWB peer online: 0x%X\n", device->getShortAddress());
  }
}

// Makerfabs callback for peers that disappear from the ranging table.
void onInactiveDevice(DW1000Device *device) {
  if (device != nullptr) {
    Serial.printf("UWB peer inactive: 0x%X\n", device->getShortAddress());
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  localInfo = findNode(LOCAL_NODE);
  if (localInfo == nullptr) {
    Serial.println(F("Invalid NODE_NAME. Use A, B, C, or D."));
    while (true) {
      delay(1000);
    }
  }

  Serial.printf("RTI node %c starting\n", LOCAL_NODE);
  strlcpy(localUwbAddress, localInfo->uwbAddress, sizeof(localUwbAddress));
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI);
  DW1000Ranging.initCommunication(PIN_RST, PIN_SS, PIN_IRQ);
  DW1000Ranging.attachNewRange(onNewRange);
  DW1000Ranging.attachNewDevice(onNewDevice);
  DW1000Ranging.attachInactiveDevice(onInactiveDevice);
  setRadioRole(RadioRole::Anchor);
}

void loop() {
  maintainWiFi();
  if (WiFi.status() == WL_CONNECTED && millis() - lastDiscoveryAttemptMs >= 5000) {
    lastDiscoveryAttemptMs = millis();
    if (strcmp(serverUrl, SERVER_FALLBACK_URL) == 0) {
      discoverServer();
    }
  }
  maintainTdmaRole();
  DW1000Ranging.loop();

  const uint32_t now = millis();
  if (now - lastHeartbeatMs >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeatMs = now;
    sendHeartbeat();
  }
}
