# Patched Makerfabs DW1000Ranging Library

This project intentionally keeps the Makerfabs `DW1000Ranging` and `DW1000`
driver API as the base. The firmware calls the same public entry points used by
the original examples:

- `DW1000Ranging.initCommunication(...)`
- `DW1000Ranging.attachNewRange(...)`
- `DW1000Ranging.attachNewDevice(...)`
- `DW1000Ranging.attachInactiveDevice(...)`
- `DW1000Ranging.startAsTag(...)`
- `DW1000Ranging.startAsAnchor(...)`
- `DW1000Ranging.loop()`

Install the Makerfabs DW1000Ranging library into the Arduino `libraries`
directory or copy the library source into this folder and rename this folder to
the library name expected by your Arduino setup. No DW1000 driver rewrite is
required for this RTI platform.

