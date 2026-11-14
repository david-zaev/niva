// Copy this file to secrets.h (same folder) and put the real key in it.
// secrets.h is in .gitignore: never commit the real key.
// Get a key on the server:  cd /opt/niva/backend && /opt/niva/venv/bin/python manage.py add-device NIVA-XXXX
// (NIVA-XXXX is the device_id the board prints over USB when it starts.)
#pragma once

#define DEVICE_KEY "replace-with-the-key-from-the-server"

// Optional: use a fixed ID instead of the one made from the MAC address
// #define DEVICE_ID_OVERRIDE "NIVA-DEMO"
