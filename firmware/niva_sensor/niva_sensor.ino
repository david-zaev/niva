// Niva soil sensor.
// Every SEND_INTERVAL_MS: read all sensors -> print one JSON line over USB (the Web Serial backup)
// -> POST the same JSON to the Niva server over HTTPS.
//
// Board: "ESP32 Dev Module". Tools -> Partition Scheme -> "Huge APP (3MB No OTA/1MB SPIFFS)":
// WiFi + HTTPS + WiFiManager fill ~90% of the default 1.2 MB app partition.
// arduino-cli: --fqbn esp32:esp32:esp32:PartitionScheme=huge_app
//
// Libraries (Arduino Library Manager):
//   OneWire, DallasTemperature, DHT sensor library (Adafruit), Adafruit Unified Sensor,
//   Adafruit BME280 Library, Adafruit BMP280 Library, ArduinoJson (v7), WiFiManager (tzapu)
//
// WiFi: with no saved WiFi the board opens the "Niva-Setup" network; join it on a phone and pick
// the WiFi (e.g. a phone hotspot). Hold BOOT for 5 s to forget the WiFi.
// LED: slow blink = setup network open, on = connected, fast blink = last send failed.
//
// A sensor that is missing or fails sends null instead of a wrong number.
// Without secrets.h the board still prints over USB, it just does not post to the server.

#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <Adafruit_BME280.h>
#include <Adafruit_BMP280.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WiFiManager.h>
#include "config.h"
#include "root_ca.h"
#if __has_include("secrets.h")
#include "secrets.h"
#endif

OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);
DHT dht(PIN_DHT, DHT22);
Adafruit_BME280 bme;
Adafruit_BMP280 bmp;
WiFiManager wm;
WiFiClientSecure tls;

enum BaroType { BARO_NONE, BARO_BMP280, BARO_BME280 };
BaroType baro = BARO_NONE;
uint8_t baroAddr = 0;
String deviceId;
unsigned long lastSend = 0;
bool lastPostFailed = false;

// ---- Readings waiting to be sent (oldest first), kept when the network is down ----
const int QUEUE_MAX = 50;
struct Pending { String body; unsigned long takenAt; };
Pending queue[QUEUE_MAX];
int qHead = 0, qCount = 0;

void enqueue(const String &body) {
  int idx = (qHead + qCount) % QUEUE_MAX;
  if (qCount == QUEUE_MAX) { qHead = (qHead + 1) % QUEUE_MAX; qCount--; }  // drop the oldest
  queue[idx] = {body, millis()};
  qCount++;
}

// "NIVA-" + last 4 hex characters of the MAC address, e.g. NIVA-A1F3
String makeDeviceId() {
#ifdef DEVICE_ID_OVERRIDE
  return String(DEVICE_ID_OVERRIDE);
#else
  uint64_t mac = ESP.getEfuseMac();               // bytes in little-endian order
  uint8_t b4 = (mac >> 32) & 0xFF, b5 = (mac >> 40) & 0xFF;
  char id[12];
  snprintf(id, sizeof(id), "NIVA-%02X%02X", b4, b5);
  return String(id);
#endif
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

String readSensorsJson() {
  int soilRaw = readSoilRaw();

  float soilTemp = NAN;
  if (ds18b20.getDeviceCount() == 0) ds18b20.begin();   // probe plugged in later
  if (ds18b20.getDeviceCount() > 0) {
    ds18b20.requestTemperatures();
    float t = ds18b20.getTempCByIndex(0);
    if (t != DEVICE_DISCONNECTED_C && t > -55 && t < 125) soilTemp = t;
  }

  // Air: BME/BMP280 first; DHT22 gives humidity when the board is a BMP280, and is the backup
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
  // Extra fields for calibration and cross-checks (the server ignores them)
  if (soilRaw >= 0) doc["soil_raw"] = soilRaw; else doc["soil_raw"] = nullptr;
  setOrNull(doc, "dht_temp_c", dhtTemp, !isnan(dhtTemp));
  doc["device_id"] = deviceId;

  String out;
  serializeJson(doc, out);
  return out;
}

// POST one reading. age_s tells the server how long ago it was measured (for queued readings).
// Returns the HTTP status, or a negative number on a network error.
int postReading(const String &body, unsigned long takenAt) {
#ifdef DEVICE_KEY
  String payload = body;
  unsigned long age = (millis() - takenAt) / 1000;
  if (age > 0) payload = body.substring(0, body.length() - 1) + ",\"age_s\":" + String(age) + "}";

  HTTPClient http;
  http.setConnectTimeout(4000);
  http.setTimeout(4000);
  if (!http.begin(tls, String(SERVER_URL) + "/readings")) return -100;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Id", deviceId);
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int code = http.POST(payload);
  http.end();
  return code;
#else
  return -200;  // no secrets.h: USB only
#endif
}

// Send queued readings oldest first; stop at the first failure and keep the rest
void flushQueue() {
  while (qCount > 0) {
    Pending &p = queue[qHead];
    int code = postReading(p.body, p.takenAt);
    if (code == 201 || code == 200 || code == 422 || code == 401) {
      // 422 (bad values) and 401 (wrong key) never succeed on retry: drop them
      if (code == 401 || code == 422) Serial.printf("{\"event\":\"post_rejected\",\"http\":%d}\n", code);
      qHead = (qHead + 1) % QUEUE_MAX;
      qCount--;
      lastPostFailed = (code != 201 && code != 200);
    } else {
      Serial.printf("{\"event\":\"post_failed\",\"http\":%d,\"queued\":%d}\n", code, qCount);
      lastPostFailed = true;
      return;
    }
  }
}

void updateLed() {
  unsigned long t = millis();
  bool on;
  if (WiFi.status() != WL_CONNECTED) on = (t / 1000) % 2;   // slow blink: setup network / no WiFi
  else if (lastPostFailed) on = (t / 150) % 2;              // fast blink: send failed
  else on = true;                                           // steady: all good
  digitalWrite(PIN_LED, on ? HIGH : LOW);
}

// Hold BOOT for 5 seconds: forget WiFi and restart into the setup network
void checkBootButton() {
  static unsigned long pressedSince = 0;
  if (digitalRead(PIN_BOOT) == LOW) {
    if (pressedSince == 0) pressedSince = millis();
    if (millis() - pressedSince > 5000) {
      Serial.println("{\"event\":\"wifi_reset\"}");
      wm.resetSettings();
      delay(200);
      ESP.restart();
    }
  } else {
    pressedSince = 0;
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BOOT, INPUT_PULLUP);
  // power the sensors from spare pins (see config.h), then give them time to start
  for (int pin : {PIN_PWR_DHT, PIN_PWR_SOIL, PIN_PWR_DS18, PIN_BARO_CSB}) { pinMode(pin, OUTPUT); digitalWrite(pin, HIGH); }
  for (int pin : {PIN_BARO_SDO, PIN_GND_EXTRA}) { pinMode(pin, OUTPUT); digitalWrite(pin, LOW); }
  delay(1500);  // the DHT22 needs about a second after power-up
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
#ifdef DEVICE_KEY
  info["server"] = SERVER_URL;
#else
  info["server"] = "off (no secrets.h)";
#endif
  serializeJson(info, Serial);
  Serial.println();

  tls.setCACert(ROOT_CA);
  WiFi.mode(WIFI_STA);
  wm.setConfigPortalBlocking(false);   // keep reading sensors and printing over USB while in setup
  wm.setConnectTimeout(20);
  if (wm.autoConnect("Niva-Setup")) {
    Serial.printf("{\"event\":\"wifi\",\"ssid\":\"%s\",\"ip\":\"%s\"}\n",
                  WiFi.SSID().c_str(), WiFi.localIP().toString().c_str());
  } else {
    Serial.println("{\"event\":\"setup_network\",\"ssid\":\"Niva-Setup\"}");
  }
}

void loop() {
  wm.process();
  checkBootButton();
  updateLed();

  if (lastSend != 0 && millis() - lastSend < SEND_INTERVAL_MS) return;
  lastSend = millis();

  String body = readSensorsJson();
  Serial.println(body);

#ifdef DEVICE_KEY
  enqueue(body);
  if (WiFi.status() == WL_CONNECTED) flushQueue();
#endif
}
