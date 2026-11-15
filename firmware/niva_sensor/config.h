// Niva sensor settings. Secrets (the device key) live in secrets.h, which is not in git.
#pragma once

// ---- Pins (ESP32-32D DevKit, all sensors on 3V3) ----
#define SOIL_ENABLED   1   // 1 = a capacitive soil moisture sensor is wired (AOUT on PIN_SOIL); 0 = sends null
#define PIN_SOIL      34   // capacitive soil sensor AOUT (analog input only)
#define SOIL2_ENABLED  0   // 1 = a second capacitive probe is wired (demo: probe 1 in the bare pot, probe 2 in the covered pot)
#define PIN_SOIL2     35   // second probe AOUT (analog input only); uses the same dry/wet calibration
#define PIN_DS18B20   14   // DS18B20 yellow wire; 4.7k resistor between yellow and the 3.3 V (+) line
#define PIN_DHT        4   // DHT22 / AM2302 DAT
#define PIN_SDA       21   // BME280 / BMP280 SDA
#define PIN_SCL       22   // BME280 / BMP280 SCL
#define PIN_LED        2   // blue on-board LED
#define PIN_BOOT       0   // BOOT button: hold 5 s to forget WiFi (M2)

// ---- Powering sensors from spare pins (wiring without a breadboard) ----
// -1 = that sensor takes 3.3 V from the breadboard's + line instead (the current build).
// Otherwise the pin is set HIGH to give the sensor 3.3 V (each draws only a few mA).
#define PIN_PWR_DHT   -1   // DHT22 VCC
#define PIN_PWR_SOIL  -1   // soil sensor VCC
#define PIN_PWR_DS18  -1   // DS18B20 red wire
#define PIN_BARO_CSB  33   // HIGH: keeps the BMP/BME280 in I2C mode
#define PIN_BARO_SDO  32   // LOW: BMP/BME280 address 0x76
#define PIN_GND_EXTRA 13   // LOW: a third ground if the board has only two GND pins

// ---- Timing ----
#define WIFI_LOST_MS 60000UL      // WiFi gone this long -> open the "Niva-Setup" network again
#define SEND_INTERVAL_MS 5000UL   // demo: 5 s. In a real field: 600000UL (10 min)

// ---- Soil calibration: raw analog values (0..4095) ----
// Day-1 calibration: hold the sensor in dry air -> SOIL_RAW_DRY,
// put it in a glass of water up to the line -> SOIL_RAW_WET.
// The raw value is printed as "soil_raw" so you can read both numbers off the Serial Monitor.
#define SOIL_RAW_DRY 4095   // NIVA-6644, 2026-11-14: dry air reads the ADC's top (3.14 V)
#define SOIL_RAW_WET 1910   // NIVA-6644, 2026-11-14: in water up to the line (1.69 V)

// ---- Server ----
#define SERVER_URL "https://niva-api.92-5-133-111.sslip.io"
// Hackathon laptop instead of the server: the laptop's WiFi address and the API port, plain http, e.g.
// #define SERVER_URL "http://192.168.1.50:8000"
