#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <utility/imumaths.h>

// System Address of the BNO055 (default is 0x28)
// You may need to change this to 0x29 if you set the ADR pin high
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);

void setup(void) {
  Serial.begin(115200); // Use a fast baud rate for best results

  while (!Serial) {
    delay(100); // Wait for serial port to open
  }

  Serial.println("BNO055 Compass Test");

  /* Initialise the sensor */
  if (!bno.begin()) {
    /* There was a problem detecting the BNO055 */
    Serial.print("Ooops, no BNO055 detected! Check your wiring or I2C ADDR!");
    while (1);
  }

  // Set to NDOF mode for sensor fusion (best for compass)
  // bno.setMode(OPERATION_MODE_NDOF); // Already the default in bno.begin()
  
  delay(1000); // Wait 1 second for the sensor to start
}

void loop(void) {
  // Read the Euler angle vector (X, Y, Z) in degrees
  imu::Vector<3> euler = bno.getVector(Adafruit_BNO055::VECTOR_EULER);

  // The X component of the Euler vector is the Yaw angle (Heading/Compass direction)
  float heading =(float)euler.x();

  Serial.print("Heading (Yaw): ");
  Serial.print(heading);
  Serial.println(" degrees");
  
  // Optional: Convert to cardinal direction
  String direction = getCardinalDirection(heading);
  Serial.print("Direction: ");
  Serial.println(direction);

  delay(100); // Delay for a smoother reading rate
}

// Simple function to convert degrees to cardinal direction
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