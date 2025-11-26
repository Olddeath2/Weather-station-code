/*theoryCIRCUIT*/
#include <Wire.h>
#include <Adafruit_BMP280.h>

Adafruit_BMP280 bmp; // I2C interface

void setup() {
  Serial.begin(115200);
  Serial.println(F("BMP280 Test"));

  // Initialize BMP280
  if (!bmp.begin(0x77)) { // Default I2C address is 0x76
    Serial.println(F("Could not find a valid BMP280 sensor, check wiring!"));
    while (1);
  }

  // Configure BMP280 settings
  bmp.setSampling(Adafruit_BMP280::MODE_NORMAL,     // Operating mode
                  Adafruit_BMP280::SAMPLING_X2,     // Temperature oversampling
                  Adafruit_BMP280::SAMPLING_X16,    // Pressure oversampling
                  Adafruit_BMP280::FILTER_X16,      // Filtering
                  Adafruit_BMP280::STANDBY_MS_500); // Standby time
}

void loop() {
  // Read temperature (°C)
  Serial.print(F("Temperature = "));
  Serial.print(bmp.readTemperature());
  Serial.println(" *C");

  // Read pressure (Pa)
  Serial.print(F("Pressure = "));
  Serial.print(bmp.readPressure()/100);
  Serial.println(" HPa");

  // Read altitude (meters, adjust sea-level pressure as needed)
  Serial.print(F("Approx altitude = "));
  Serial.print(bmp.readAltitude(1013.25)); // Standard sea-level pressure
  Serial.println(" m");

  Serial.println();
  delay(2000); // Wait 2 seconds before next reading
}