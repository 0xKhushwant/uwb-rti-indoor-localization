#pragma once

#include <Arduino.h>

constexpr uint8_t NODE_COUNT = 4;
constexpr uint8_t LINK_COUNT = 6;
constexpr uint32_t TDMA_CYCLE_MS = 8000;
constexpr uint32_t TDMA_SLOT_MS = 2000;
constexpr uint32_t HEARTBEAT_INTERVAL_MS = 1000;
constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 5000;
constexpr uint32_t HTTP_TIMEOUT_MS = 700;
constexpr uint32_t SLOT_GUARD_MS = 200;
constexpr float MIN_VALID_RANGE_M = 0.05F;
constexpr float MAX_VALID_RANGE_M = 40.0F;
constexpr size_t JSON_BUFFER_SIZE = 256;

constexpr int PIN_RST = 27;
constexpr int PIN_SS = 4;
constexpr int PIN_IRQ = 34;
constexpr int PIN_SPI_SCK = 18;
constexpr int PIN_SPI_MISO = 19;
constexpr int PIN_SPI_MOSI = 23;

struct NodeInfo {
  char name;
  const char *uwbAddress;
  uint16_t shortAddress;
};

struct LinkInfo {
  char source;
  char target;
  const char *name;
};

struct RangingSample {
  char source = '?';
  char target = '?';
  float range = 0.0F;
  float rxPower = 0.0F;
  float fpPower = 0.0F;
  uint32_t timestamp = 0;
  bool valid = false;
};

constexpr NodeInfo NODES[NODE_COUNT] = {
    {'A', "A1:00:22:EA:82:60:3B:A1", 0x00A1},
    {'B', "B1:00:22:EA:82:60:3B:B1", 0x00B1},
    {'C', "C1:00:22:EA:82:60:3B:C1", 0x00C1},
    {'D', "D1:00:22:EA:82:60:3B:D1", 0x00D1},
};

constexpr LinkInfo LINKS[LINK_COUNT] = {
    {'A', 'B', "A-B"},
    {'A', 'C', "A-C"},
    {'A', 'D', "A-D"},
    {'B', 'C', "B-C"},
    {'B', 'D', "B-D"},
    {'C', 'D', "C-D"},
};

inline const NodeInfo *findNode(char name) {
  for (uint8_t i = 0; i < NODE_COUNT; ++i) {
    if (NODES[i].name == name) {
      return &NODES[i];
    }
  }
  return nullptr;
}

inline const NodeInfo *findNodeByShortAddress(uint16_t shortAddress) {
  for (uint8_t i = 0; i < NODE_COUNT; ++i) {
    if (NODES[i].shortAddress == shortAddress) {
      return &NODES[i];
    }
  }
  return nullptr;
}

inline const char *linkName(char source, char target) {
  for (uint8_t i = 0; i < LINK_COUNT; ++i) {
    if (LINKS[i].source == source && LINKS[i].target == target) {
      return LINKS[i].name;
    }
  }
  return "";
}

inline bool isScheduledTarget(char source, char target) {
  return linkName(source, target)[0] != '\0';
}

inline char initiatorForSlot(uint8_t slot) {
  switch (slot) {
    case 0:
      return 'A';
    case 1:
      return 'B';
    case 2:
      return 'C';
    default:
      return '-';
  }
}
