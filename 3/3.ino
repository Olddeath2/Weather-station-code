const int sensorPin = 4; // Use GPIO 4 (ADC1)

void setup() {
  Serial.begin(115200);

  // Set attenuation to 11dB to allow reading up to ~3.1V
  // This covers your 2.5V max output comfortably.
  analogSetAttenuation(ADC_11db);
}

void loop() {
  // Get the voltage directly in millivolts (uses factory calibration)
  uint32_t voltage_mV = analogReadMilliVolts(sensorPin);
  
  // Convert to Volts for display
  float voltage_V = voltage_mV / 1000.0;
  float windspeed_kmph =voltage_V*50.0;
  float windspeed_mps=voltage_V*14;
  //Serial.printf("Measured: %.3f V\n", voltage_V);
  Serial.printf("Windspeed: %.3f KM/H\n", windspeed_kmph);
 Serial.printf("Windspeed: %.3f m/s\n", windspeed_mps);
  delay(500);
}