// Niva soil sensor: reads every sensor and prints one JSON line over USB every SEND_INTERVAL_MS.
// The same JSON line is what the web app's Web Serial backup reads, and what M2 sends to the server.
//
// Libraries (Arduino Library Manager):
//   OneWire, DallasTemperature, DHT sensor library (Adafruit), Adafruit Unified Sensor,
//   Adafruit BME280 Library, Adafruit BMP280 Library, ArduinoJson (v7)
//
// A sensor that is missing or fails sends null instead of a wrong number.

#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <Adafruit_BME280.h>
#include <Adafruit_BMP280.h>
#include <ArduinoJson.h>
#include "config.h"

OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);
DHT dht(PIN_DHT, DHT22);
Adafruit_BME280 bme;
Adafruit_BMP280 bmp;

enum BaroType { BARO_NONE, BARO_BMP280, BARO_BME280 };
BaroType baro = BARO_NONE;
uint8_t baroAddr = 0;
String deviceId;
unsigned long lastSend = 0;

// "NIVA-" + last 4 hex characters of the MAC address, e.g. NIVA-A1F3
String makeDeviceId() {
  uint64_t mac = ESP.getEfuseMac();               // bytes in little-endian order
  uint8_t b4 = (mac >> 32) & 0xFF, b5 = (mac >> 40) & 0xFF;
  char id[12];
  snprintf(id, sizeof(id), "NIVA-%02X%02X", b4, b5);
  return String(id);
}

// Read the chip ID at 0xD0: 0x60 = BME280 (has humidity), 0x58 = BMP280 (no humidity)
uint8_t readChipId(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(0xD0);
  if (Wire.endTransmission() != 0) return 0;
  if (Wire.requestFrom(addr, (uint8_t)1) != 1) return 0;
  return Wire.read();
}

void detectBaro() {
  const uint8_t addrs[] = {0x76, 0x77};
  for (uint8_t addr : addrs) {
    uint8_t chip = readChipId(addr);
    if (chip == 0x60 && bme.begin(addr, &Wire)) { baro = BARO_BME280; baroAddr = addr; return; }
    if (chip == 0x58 && bmp.begin(addr, chip)) { baro = BARO_BMP280; baroAddr = addr; return; }
  }
}

// Average 16 samples; returns -1 if the pin looks unconnected (stuck at 0 or 4095)
int readSoilRaw() {
  long sum = 0;
  for (int i = 0; i < 16; i++) { sum += analogRead(PIN_SOIL); delay(2); }
  int raw = sum / 16;
  return (raw <= 5 || raw >= 4090) ? -1 : raw;
}

// Lower raw = wetter on capacitive sensors
float soilPercent(int raw) {
  float pct = 100.0f * (SOIL_RAW_DRY - raw) / (float)(SOIL_RAW_DRY - SOIL_RAW_WET);
  return constrain(pct, 0.0f, 100.0f);
}

float round1(float v) { return roundf(v * 10.0f) / 10.0f; }

void setOrNull(JsonDocument &doc, const char *key, float v, bool ok) {
  if (ok) doc[key] = round1(v);
  else doc[key] = nullptr;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_LED, OUTPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_SOIL, ADC_11db);   // full 0..3.3 V range

  Wire.begin(PIN_SDA, PIN_SCL);
  ds18b20.begin();
  dht.begin();
  detectBaro();
  deviceId = makeDeviceId();

  // One info line at start-up so wiring problems are obvious
  JsonDocument info;
  info["event"] = "boot";
  info["device_id"] = deviceId;
  info["ds18b20_count"] = ds18b20.getDeviceCount();
  info["baro"] = baro == BARO_BME280 ? "BME280" : baro == BARO_BMP280 ? "BMP280" : "none";
  if (baro != BARO_NONE) info["baro_addr"] = baroAddr == 0x76 ? "0x76" : "0x77";
  serializeJson(info, Serial);
  Serial.println();
}

void loop() {
  if (millis() - lastSend < SEND_INTERVAL_MS && lastSend != 0) return;
  lastSend = millis();
  digitalWrite(PIN_LED, HIGH);

  // Soil moisture
  int soilRaw = readSoilRaw();

  // Soil temperature (DS18B20)
  float soilTemp = NAN;
  if (ds18b20.getDeviceCount() == 0) ds18b20.begin();   // probe plugged in later
  if (ds18b20.getDeviceCount() > 0) {
    ds18b20.requestTemperatures();
    float t = ds18b20.getTempCByIndex(0);
    if (t != DEVICE_DISCONNECTED_C && t > -55 && t < 125) soilTemp = t;
  }

  // Air: BME/BMP280 first, DHT22 for humidity when the board is a BMP280, and as backup
  float baroTemp = NAN, baroHum = NAN, pressure = NAN;
  if (baro == BARO_BME280) {
    baroTemp = bme.readTemperature();
    baroHum = bme.readHumidity();
    pressure = bme.readPressure() / 100.0f;
  } else if (baro == BARO_BMP280) {
    baroTemp = bmp.readTemperature();
    pressure = bmp.readPressure() / 100.0f;
  }
  float dhtTemp = dht.readTemperature();
  float dhtHum = dht.readHumidity();

  float airTemp = !isnan(baroTemp) ? baroTemp : dhtTemp;
  float humidity = !isnan(baroHum) ? baroHum : dhtHum;
  bool pressureOk = !isnan(pressure) && pressure > 300 && pressure < 1100;

  JsonDocument doc;
  setOrNull(doc, "soil_pct", soilRaw >= 0 ? soilPercent(soilRaw) : NAN, soilRaw >= 0);
  setOrNull(doc, "soil_temp_c", soilTemp, !isnan(soilTemp));
  setOrNull(doc, "air_temp_c", airTemp, !isnan(airTemp));
  setOrNull(doc, "humidity_pct", humidity, !isnan(humidity) && humidity >= 0 && humidity <= 100);
  setOrNull(doc, "pressure_hpa", pressure, pressureOk);
  doc["battery_v"] = nullptr;
  // Extra fields for calibration and checking sensors against each other
  if (soilRaw >= 0) doc["soil_raw"] = soilRaw; else doc["soil_raw"] = nullptr;
  setOrNull(doc, "dht_temp_c", dhtTemp, !isnan(dhtTemp));
  doc["device_id"] = deviceId;

  serializeJson(doc, Serial);
  Serial.println();
  digitalWrite(PIN_LED, LOW);
}
