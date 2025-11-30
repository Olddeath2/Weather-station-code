
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_BMP280.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>
#include <esp_sleep.h>
#include <ArduinoJson.h>
#include <utility/imumaths.h>

// ========== CONFIGURATION ==========
// WiFi Credentials
const char* WIFI_SSID = "";
const char* WIFI_PASSWORD = "";

// MQTT Broker
const char* MQTT_BROKER = "";  
const int MQTT_PORT = 8883;
const char* MQTT_USER = "";  
const char* MQTT_PASSWORD = "";

// Device ID
const char* DEVICE_ID = "sensor_node001";

// Pin Definitions
#define DHT_PIN 21
#define GPS_RX_PIN 20
#define GPS_TX_PIN 19
#define ANEMOMETER_PIN 4  // ADC pin
#define LED_PIN 2  // Built-in LED

// I2C Addresses
#define BNO055_ADDRESS 0x28
#define BMP280_ADDRESS 0x77

// Sensor Reading Intervals (milliseconds)
#define GPS_INTERVAL_HP 15000        // 15 seconds in high-power
#define GPS_INTERVAL_SLEEP 900000    // 15 minutes in sleep
#define ENV_INTERVAL_HP 5000         // 5 seconds in high-power
#define ENV_INTERVAL_SLEEP 300000    // 5 minutes in sleep
#define IMU_INTERVAL_HP 1000         // 1 second in high-power
#define IMU_INTERVAL_SLEEP 60000     // 1 minute in sleep
#define ANEM_SAMPLE_INTERVAL 1000    // 1 second sampling
#define ANEM_ACTIVE_PERIOD 300000    // 5 minutes ON
#define ANEM_SLEEP_PERIOD 300000     // 5 minutes OFF

// ========== GLOBAL OBJECTS ==========
WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);
DHT dht(DHT_PIN, DHT11);
Adafruit_BNO055 bno = Adafruit_BNO055(55, BNO055_ADDRESS);
Adafruit_BMP280 bmp;
TinyGPSPlus gps;
HardwareSerial gpsSerial(1);

// ========== SENSOR NODE CLASS ==========
class SensorNode {
private:
  // Operational mode
  enum Mode {
    HIGH_POWER,
    SLEEP_MODE
  };
  Mode currentMode;
  
  // Sensor status flags
  bool dht11_ok;
  bool bmp280_ok;
  bool bno055_ok;
  bool gps_ok;
  bool anemometer_ok;
  
  // Timing variables
  unsigned long lastGPSRead;
  unsigned long lastEnvRead;
  unsigned long lastIMURead;
  unsigned long anemometerStartTime;
  bool anemometerActive;
  
  // Anemometer data
  float anemometerReadings[300];  // Max 5 min * 60 = 300 samples
  int anemometerSampleCount;
  unsigned long lastAnemometerSample;
  
  // LED blinking
  unsigned long lastLEDBlink;
  bool ledState;
  
  // Connection status
  bool wifiConnected;
  bool mqttConnected;

public:
  SensorNode() {
    currentMode = HIGH_POWER;
    dht11_ok = false;
    bmp280_ok = false;
    bno055_ok = false;
    gps_ok = false;
    anemometer_ok = false;
    
    lastGPSRead = 0;
    lastEnvRead = 0;
    lastIMURead = 0;
    anemometerStartTime = 0;
    anemometerActive = true;
    anemometerSampleCount = 0;
    lastAnemometerSample = 0;
    
    lastLEDBlink = 0;
    ledState = false;
    
    wifiConnected = false;
    mqttConnected = false;
  }
  
  void begin() {
    Serial.begin(115200);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    
    Serial.println("Initializing Sensor Node...");
    
    // Initialize I2C
    Wire.begin();
    
    // Initialize DHT11
    dht.begin();
    dht11_ok = true;
    Serial.println("DHT11 initialized");
    
    // Initialize BMP280
    if (bmp.begin(BMP280_ADDRESS)) {
      bmp280_ok = true;
      Serial.println("BMP280 initialized");
    } else {
      Serial.println("BMP280 initialization failed");
    }
    
    // Initialize BNO055
    if (bno.begin()) {
      bno055_ok = true;
      bno.setExtCrystalUse(true);
      Serial.println("BNO055 initialized");
    } else {
      Serial.println("BNO055 initialization failed");
    }
    
    // Initialize GPS (keep powered continuously)
    gpsSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
    gps_ok = true;
    Serial.println("GPS initialized (continuous power)");
    
    // Initialize Anemometer
    pinMode(ANEMOMETER_PIN, INPUT);
    anemometer_ok = true;
    Serial.println("Anemometer initialized");
    
    // Connect WiFi
    connectWiFi();
    

    espClient.setInsecure();  
    
    // Setup MQTT
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setKeepAlive(60);
    mqttClient.setSocketTimeout(30);
    mqttClient.setBufferSize(512);
    mqttClient.setCallback([this](char* topic, byte* payload, unsigned int length) {
      this->mqttCallback(topic, payload, length);
    });
    
    delay(2000);  // Give WiFi time to stabilize
    connectMQTT();
    
    // Subscribe to mode command
    String cmdTopic = String(DEVICE_ID) + "/command/mode";
    mqttClient.subscribe(cmdTopic.c_str());
    
    checkAllSensorsStatus();
  }
  
  void loop() {
    unsigned long currentMillis = millis();
    
    // 1. Ensure WiFi is connected (retry until connected)
    if (WiFi.status() != WL_CONNECTED) {
      wifiConnected = false;
      Serial.println("WiFi disconnected! Reconnecting...");
      connectWiFi();
    } else {
      wifiConnected = true;
    }
    
    // 2. Ensure MQTT is connected (retry until connected)
    if (!mqttClient.connected()) {
      mqttConnected = false;
      Serial.println("MQTT disconnected! Reconnecting...");
      connectMQTT();
    } else {
      mqttConnected = true;
    }
    
    // 3. Process MQTT messages
    mqttClient.loop();
    
    // 4. Update LED status
    updateLED();
    
    // 5. Read sensors and publish data
    // Get current intervals based on mode
    unsigned long gpsInterval = (currentMode == HIGH_POWER) ? GPS_INTERVAL_HP : GPS_INTERVAL_SLEEP;
    unsigned long envInterval = (currentMode == HIGH_POWER) ? ENV_INTERVAL_HP : ENV_INTERVAL_SLEEP;
    unsigned long imuInterval = (currentMode == HIGH_POWER) ? IMU_INTERVAL_HP : IMU_INTERVAL_SLEEP;
    
    // Read GPS
    if (currentMillis - lastGPSRead >= gpsInterval) {
      readGPS();
      lastGPSRead = currentMillis;
    }
    
    // Read Environmental sensors
    if (currentMillis - lastEnvRead >= envInterval) {
      readEnvironmental();
      lastEnvRead = currentMillis;
    }
    
    // Read IMU
    if (currentMillis - lastIMURead >= imuInterval) {
      readIMU();
      lastIMURead = currentMillis;
    }
    
    // Handle Anemometer sampling cycle
    handleAnemometer(currentMillis);
    
    // Feed GPS with available data
    while (gpsSerial.available() > 0) {
      gps.encode(gpsSerial.read());
    }
  }

private:
  void connectWiFi() {
    Serial.print("Connecting to WiFi");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    // Keep trying until connected
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
    }
    
    Serial.println("\nWiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    wifiConnected = true;
  }
  
  void connectMQTT() {
    Serial.print("Connecting to MQTT...");
    
    // Keep trying until connected
    while (!mqttClient.connected()) {
      if (mqttClient.connect(DEVICE_ID, MQTT_USER, MQTT_PASSWORD)) {
        Serial.println("Connected!");
        mqttConnected = true;
        
        // Subscribe to command topic
        String cmdTopic = String(DEVICE_ID) + "/command/mode";
        mqttClient.subscribe(cmdTopic.c_str());
        Serial.print("Subscribed to: ");
        Serial.println(cmdTopic);
      } else {
        Serial.print("Failed, rc=");
        Serial.print(mqttClient.state());
        Serial.println(" Retrying in 2 seconds...");
        delay(2000);
      }
    }
  }
  
  void mqttCallback(char* topic, byte* payload, unsigned int length) {
    String message;
    for (unsigned int i = 0; i < length; i++) {
      message += (char)payload[i];
    }
    
    Serial.print("Message received on ");
    Serial.print(topic);
    Serial.print(": ");
    Serial.println(message);
    
    // Handle mode command
    String cmdTopic = String(DEVICE_ID) + "/command/mode";
    if (String(topic) == cmdTopic) {
      if (message == "sleep") {
        currentMode = SLEEP_MODE;
        Serial.println("Mode changed to SLEEP");
      } else if (message == "high_power") {
        currentMode = HIGH_POWER;
        Serial.println("Mode changed to HIGH_POWER");
      }
    }
  }
  
  void readGPS() {
    Serial.println("Reading GPS...");
    
    // Check if GPS has valid data
    if (gps.location.isValid()) {
      StaticJsonDocument<256> doc;
      
      doc["latitude"] = gps.location.lat();
      doc["longitude"] = gps.location.lng();
      doc["altitude"] = gps.altitude.meters();
      doc["satellites"] = gps.satellites.value();
      doc["status"] = "ok";
      
      String topic = String(DEVICE_ID) + "/gps";
      publishJSON(topic.c_str(), doc);
      
      gps_ok = true;
    } else {
      Serial.println("GPS: Waiting for fix...");
      
      StaticJsonDocument<128> doc;
      doc["status"] = "error";
      doc["message"] = "No GPS fix";
      
      String topic = String(DEVICE_ID) + "/gps";
      publishJSON(topic.c_str(), doc);
      
      gps_ok = false;
    }
  }
  
  void readEnvironmental() {
    Serial.println("Reading Environmental sensors...");
    
    // Read DHT11
    float tempDHT = dht.readTemperature();
    float humidity = dht.readHumidity();
    
    // Read BMP280
    float tempBMP = bmp280_ok ? bmp.readTemperature() : NAN;
    float pressure = bmp280_ok ? bmp.readPressure() / 100.0F : NAN;  // Convert Pa to hPa
    
    // Publish Temperature (averaged)
    if (!isnan(tempDHT) || !isnan(tempBMP)) {
      StaticJsonDocument<256> doc;
      
      // Calculate average temperature
      float avgTemp = 0;
      int tempCount = 0;
      if (!isnan(tempDHT)) {
        avgTemp += tempDHT;
        tempCount++;
        doc["temp_dht11"] = tempDHT;
      }
      if (!isnan(tempBMP)) {
        avgTemp += tempBMP;
        tempCount++;
        doc["temp_bmp280"] = tempBMP;
      }
      
      if (tempCount > 0) {
        avgTemp /= tempCount;
        doc["temperature"] = avgTemp;
        doc["status"] = "ok";
      } else {
        doc["status"] = "error";
        doc["message"] = "No temperature data";
      }
      
      String topic = String(DEVICE_ID) + "/temperature";
      publishJSON(topic.c_str(), doc);
      
      dht11_ok = !isnan(tempDHT);
    } else {
      StaticJsonDocument<128> doc;
      doc["status"] = "error";
      doc["message"] = "Temperature sensors failed";
      
      String topic = String(DEVICE_ID) + "/temperature";
      publishJSON(topic.c_str(), doc);
      
      dht11_ok = false;
    }
    
    // Publish Humidity
    if (!isnan(humidity)) {
      StaticJsonDocument<128> doc;
      doc["humidity"] = humidity;
      doc["status"] = "ok";
      
      String topic = String(DEVICE_ID) + "/humidity";
      publishJSON(topic.c_str(), doc);
    } else {
      StaticJsonDocument<128> doc;
      doc["status"] = "error";
      doc["message"] = "DHT11 humidity read failed";
      
      String topic = String(DEVICE_ID) + "/humidity";
      publishJSON(topic.c_str(), doc);
    }
    
    // Publish Pressure
    if (!isnan(pressure)) {
      StaticJsonDocument<128> doc;
      doc["pressure"] = pressure;
      doc["status"] = "ok";
      
      String topic = String(DEVICE_ID) + "/pressure";
      publishJSON(topic.c_str(), doc);
      
      bmp280_ok = true;
    } else {
      StaticJsonDocument<128> doc;
      doc["status"] = "error";
      doc["message"] = "BMP280 pressure read failed";
      
      String topic = String(DEVICE_ID) + "/pressure";
      publishJSON(topic.c_str(), doc);
      
      bmp280_ok = false;
    }
  }
      String getCardinalDirection(float degrees) {
  if (degrees > 337.5 || degrees <= 22.5) return "N";
  if (degrees > 22.5 && degrees <= 67.5) return "NE";
  if (degrees > 67.5 && degrees <= 112.5) return "E";
  if (degrees > 112.5 && degrees <= 157.5) return "SE";
  if (degrees > 157.5 && degrees <= 202.5) return "S";
  if (degrees > 202.5 && degrees <= 247.5) return "SW";
  if (degrees > 247.5 && degrees <= 292.5) return "W";
  if (degrees > 292.5 && degrees <= 337.5) return "NW";
  return "?";
}
  void readIMU() {

    Serial.println("Reading IMU...");
    
    if (!bno055_ok) {
      // Try to reinitialize
      if (bno.begin()) {
        bno055_ok = true;
        bno.setExtCrystalUse(true);
        Serial.println("BNO055 reconnected!");
      } else {
        StaticJsonDocument<128> doc;
        doc["status"] = "error";
        doc["message"] = "BNO055 not responding";
        
        String topic = String(DEVICE_ID) + "/imu";
        publishJSON(topic.c_str(), doc);
        return;
      }
    }
    imu::Vector<3> euler = bno.getVector(Adafruit_BNO055::VECTOR_EULER);  
    float heading =(float)euler.x();
     String direction = getCardinalDirection(heading);
    // Get orientation data
    sensors_event_t event;
    bno.getEvent(&event);
    
    StaticJsonDocument<256> doc;
    doc["Direction"] = direction;
    doc["status"] = "ok";
    
    String topic = String(DEVICE_ID) + "/imu";
    publishJSON(topic.c_str(), doc);
  }
  
  void handleAnemometer(unsigned long currentMillis) {
    // Check if we need to switch anemometer state
    if (anemometerActive) {
      // Currently sampling
      if (currentMillis - anemometerStartTime >= ANEM_ACTIVE_PERIOD) {
        // End of active period - publish results
        publishAnemometerData();
        anemometerActive = false;
        anemometerStartTime = currentMillis;
        anemometerSampleCount = 0;
        Serial.println("Anemometer: Entering sleep period");
      } else {
        // Continue sampling
        if (currentMillis - lastAnemometerSample >= ANEM_SAMPLE_INTERVAL) {
          readAnemometer();
          lastAnemometerSample = currentMillis;
        }
      }
    } else {
      // Currently in sleep period
      if (currentMillis - anemometerStartTime >= ANEM_SLEEP_PERIOD) {
        // Start new active period
        anemometerActive = true;
        anemometerStartTime = currentMillis;
        Serial.println("Anemometer: Starting active sampling period");
      }
    }
  }
  
  void readAnemometer() {
    // Read analog voltage from anemometer
    int adcValue = analogRead(ANEMOMETER_PIN);
    float voltage = (adcValue / 4095.0) * 3.3;  // ESP32 ADC is 12-bit, Vref = 3.3V
    
    // ===== WIND SPEED CALIBRATION SPACE =====
    // TODO: Add your voltage-to-windspeed conversion formula here
    // Example: float windSpeed = voltage * CALIBRATION_FACTOR + OFFSET;
    float windSpeed = voltage*50;  // Placeholder - replace with your formula
    // ========================================
    
    if (anemometerSampleCount < 300) {
      anemometerReadings[anemometerSampleCount] = windSpeed;
      anemometerSampleCount++;
    }
  }
  
  void publishAnemometerData() {
    if (anemometerSampleCount == 0) {
      StaticJsonDocument<128> doc;
      doc["status"] = "error";
      doc["message"] = "No anemometer samples";
      
      String topic = String(DEVICE_ID) + "/wind";
      publishJSON(topic.c_str(), doc);
      return;
    }
    
    // Calculate statistics
    float sum = 0;
    float minSpeed = anemometerReadings[0];
    float maxSpeed = anemometerReadings[0];
    
    for (int i = 0; i < anemometerSampleCount; i++) {
      sum += anemometerReadings[i];
      if (anemometerReadings[i] < minSpeed) minSpeed = anemometerReadings[i];
      if (anemometerReadings[i] > maxSpeed) maxSpeed = anemometerReadings[i];
    }
    
    float avgSpeed = sum / anemometerSampleCount;
    
    StaticJsonDocument<256> doc;
    doc["avg_speed"] = avgSpeed;
    doc["min_speed"] = minSpeed;
    doc["max_speed"] = maxSpeed;
    doc["samples"] = anemometerSampleCount;
    doc["status"] = "ok";
    
    String topic = String(DEVICE_ID) + "/wind";
    publishJSON(topic.c_str(), doc);
    
    Serial.print("Anemometer data published - Avg: ");
    Serial.print(avgSpeed);
    Serial.print(" Min: ");
    Serial.print(minSpeed);
    Serial.print(" Max: ");
    Serial.println(maxSpeed);
  }
  
  void publishJSON(const char* topic, JsonDocument& doc) {
    char buffer[512];
    serializeJson(doc, buffer);
    
    if (mqttClient.publish(topic, buffer)) {
      Serial.print("Published to ");
      Serial.print(topic);
      Serial.print(": ");
      Serial.println(buffer);
    } else {
      Serial.print("Failed to publish to ");
      Serial.println(topic);
    }
  }
  
  void checkAllSensorsStatus() {
    bool allFailed = !dht11_ok && !bmp280_ok && !bno055_ok && !gps_ok && !anemometer_ok;
    
    if (allFailed) {
      Serial.println("CRITICAL: All sensors failed!");
    }
  }
  
  void updateLED() {
    unsigned long currentMillis = millis();
    
    // Check if all sensors failed
    bool allFailed = !dht11_ok && !bmp280_ok && !bno055_ok && !gps_ok && !anemometer_ok;
    
    if (allFailed) {
      // Solid ON for all sensors failed
      digitalWrite(LED_PIN, HIGH);
    } else if (!wifiConnected || !mqttConnected) {
      // Blink for connection issues
      if (currentMillis - lastLEDBlink >= 500) {
        ledState = !ledState;
        digitalWrite(LED_PIN, ledState);
        lastLEDBlink = currentMillis;
      }
    } else {
      // Normal operation - LED OFF
      digitalWrite(LED_PIN, LOW);
    }
  }
};

// ========== MAIN PROGRAM ==========
SensorNode node;

void setup() {
  node.begin();
}

void loop() {
  node.loop();
}
