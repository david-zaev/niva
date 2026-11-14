// Niva sensor settings. Secrets (the device key) live in secrets.h, which is not in git.
#pragma once

// ---- Pins (ESP32-32D DevKit, all sensors on 3V3) ----
#define PIN_SOIL      34   // capacitive soil sensor AOUT (analog input only)
#define PIN_DS18B20    4   // DS18B20 yellow wire, 4.7k pull-up to 3V3
#define PIN_DHT       27   // DHT22 / AM2302 DAT
#define PIN_SDA       21   // BME280 / BMP280 SDA
#define PIN_SCL       22   // BME280 / BMP280 SCL
#define PIN_LED        2   // blue on-board LED
#define PIN_BOOT       0   // BOOT button: hold 5 s to forget WiFi (M2)

// ---- Timing ----
#define SEND_INTERVAL_MS 5000UL   // demo: 5 s. In a real field: 600000 (10 min)

// ---- Soil calibration: raw analog values (0..4095) ----
// Day-1 calibration: hold the sensor in dry air -> SOIL_RAW_DRY,
// put it in a glass of water up to the line -> SOIL_RAW_WET.
// The raw value is printed as "soil_raw" so you can read both numbers off the Serial Monitor.
#define SOIL_RAW_DRY 3300   // placeholder: replace with your measured value
#define SOIL_RAW_WET 1300   // placeholder: replace with your measured value

// ---- Server ----
#define SERVER_URL "https://niva-api.92-5-133-111.sslip.io"
