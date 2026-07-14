#pragma once

// Flash each board with only this line changed: "A", "B", "C", or "D".
#define NODE_NAME "D"

// Boards discover the Flask server by UDP broadcast. This fallback is used only
// when discovery is blocked by firewall or hotspot client isolation.
#define SERVER_FALLBACK_URL "http://10.255.226.47:5000/api/ingest"

#define DISCOVERY_PORT 50505
#define DISCOVERY_REQUEST "RTI_DISCOVER"
#define DISCOVERY_RESPONSE_PREFIX "RTI_SERVER "
