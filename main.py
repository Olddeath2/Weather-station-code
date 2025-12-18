# main.py - Updated version
import sys
import json
import ssl
from datetime import datetime

import paho.mqtt.client as mqtt

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QVBoxLayout
from PyQt5.QtCore import QTimer, Qt

from windcompass import WindCompass
from temperature_graph import TemperatureGraph 
from weather_database import WeatherDatabase  
# -------- CONFIG - set these to match your HiveMQ gateway ----------------
MQTT_BROKER = "6dee21bc18054d9db4d08e6a88cad0ca.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "RaspberryPi"
MQTT_PASSWORD = "A123a321"
SUBSCRIBE_TOPIC = "cloud/processed"

# GPS topic
GPS_TOPIC = "sensor_node001/gps"

# Handshake topics
HANDSHAKE_REQUEST_TOPIC = "gateway/handshake/request"
HANDSHAKE_RESPONSE_TOPIC = "gateway/handshake/response"
# -------------------------------------------------------------------------

# Cardinal conversion (also supports single-letter and two-letter)
_cardinal_map = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
    "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5
}

def convert_cardinal_to_angle(cardinal: str) -> float:
    if not cardinal or not isinstance(cardinal, str):
        return 0.0
    key = cardinal.strip().upper()
    return _cardinal_map.get(key, 0.0)


class WeatherDashboard:
    def __init__(self, ui_filename="UI.ui", db_path="weather_data.db"):
        # Qt app and load UI
        self.app = QApplication(sys.argv)
        self.window = uic.loadUi(ui_filename)

        # Initialize database (this creates the file and tables automatically)
        try:
            self.db = WeatherDatabase(db_path)
            print(f"✓ Database initialized: {db_path}")
        except Exception as e:
            print(f"✗ Database initialization failed: {e}")
            self.db = None
        
        self.current_session_id = None

        # Create and attach wind compass
        self.compass = WindCompass(self.window.windDirectionWidget)
        comp_layout = QVBoxLayout(self.window.windDirectionWidget)
        comp_layout.setContentsMargins(0, 0, 0, 0)
        comp_layout.addWidget(self.compass)

        # Create and attach temperature graph (NEW!)
        self.temp_graph = TemperatureGraph(width=5, height=3, dpi=100, max_samples=300)
        plot_layout = QVBoxLayout(self.window.tempGraphWidget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.addWidget(self.temp_graph)

        # MQTT client (do NOT auto-connect - connect on button press)
        self.client = mqtt.Client()
        # TLS
        self.client.tls_set()  # use system default CA certs
        # If you must skip certificate checks (not recommended), uncomment:
        # self.client.tls_insecure_set(True)

        # Set username/password if broker requires auth
        self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        # Connect button - user requested "connect only after pressing button"
        self.window.button_connect.clicked.connect(self._on_connect_button)

        # status label initial
        try:
            self.window.label_mqtt_status.setText("Disconnected")
            self.window.label_mqtt_status.setStyleSheet("color: red;")
        except Exception:
            pass

        # timer to refresh graph
        self.refresh_timer = QTimer()
        self.refresh_timer.setInterval(400)  # ms
        self.refresh_timer.timeout.connect(self._refresh_plots)
        self.refresh_timer.start()

        # track connection state
        self._connected = False
        
        # track gateway handshake info (single handshake per connection)
        self.handshake_completed = False
        self.gateway_queue_size = 0

    # ---------------- MQTT handlers ----------------
    def _on_connect_button(self):
        """Called when user presses Connect button."""
        try:
            self.window.label_mqtt_status.setText("Connecting...")
            self.window.label_mqtt_status.setStyleSheet("color: orange;")
        except Exception:
            pass

        try:
            # start network loop in background thread
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            print("MQTT connect failed:", e)
            try:
                self.window.label_mqtt_status.setText("Error")
                self.window.label_mqtt_status.setStyleSheet("color: red;")
            except Exception:
                pass

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("MQTT connected (rc=0)")
            self._connected = True
            self.handshake_completed = False
            
            # Create new session in database
            if self.db:
                self.current_session_id = self.db.create_session()
            
            # Subscribe to all topics
            client.subscribe(SUBSCRIBE_TOPIC)
            client.subscribe(GPS_TOPIC)  # Subscribe to GPS topic
            client.subscribe(HANDSHAKE_REQUEST_TOPIC)
            
            print(f"✓ Subscribed to: {SUBSCRIBE_TOPIC}")
            print(f"✓ Subscribed to: {GPS_TOPIC}")
            
            try:
                self.window.label_mqtt_status.setText("Connected")
                self.window.label_mqtt_status.setStyleSheet("color: green;")
            except Exception:
                pass
        else:
            print("MQTT connect returned code", rc)
            try:
                self.window.label_mqtt_status.setText(f"ConnErr {rc}")
                self.window.label_mqtt_status.setStyleSheet("color: red;")
            except Exception:
                pass

    def _on_disconnect(self, client, userdata, rc):
        print("MQTT disconnected, rc=", rc)
        self._connected = False
        self.handshake_completed = False
        
        # Close session in database
        if self.db and self.current_session_id:
            self.db.close_session(self.current_session_id)
            self.current_session_id = None
        
        try:
            self.window.label_mqtt_status.setText("Disconnected")
            self.window.label_mqtt_status.setStyleSheet("color: red;")
        except Exception:
            pass

    def _send_handshake_response(self):
        """Send handshake acknowledgment to gateway (only once)"""
        response = {
            "dashboard_id": "PyQt_Dashboard",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ready"
        }
        try:
            self.client.publish(HANDSHAKE_RESPONSE_TOPIC, json.dumps(response))
            print(f"[HANDSHAKE] ✓ Sent response to gateway")
            self.handshake_completed = True
        except Exception as e:
            print(f"[HANDSHAKE] Error sending response: {e}")

    def _on_message(self, client, userdata, msg):
        """
        Incoming messages arrive here.
        - Handle handshake requests from gateway (ONCE per connection)
        - Handle GPS data from sensor_node001/gps
        - Parse JSON and store in database
        - Update UI
        """
        
        # Handle handshake request from gateway (only respond once)
        if msg.topic == HANDSHAKE_REQUEST_TOPIC:
            if self.handshake_completed:
                print("[HANDSHAKE] Already completed, ignoring duplicate request")
                return
                
            try:
                payload = msg.payload.decode("utf-8", errors="ignore")
                handshake_data = json.loads(payload)
                gateway_id = handshake_data.get("gateway_id", "unknown")
                queue_size = handshake_data.get("queue_size", 0)
                
                print(f"[HANDSHAKE] Request from {gateway_id}, queue size: {queue_size}")
                
                self.gateway_queue_size = queue_size
                self._send_handshake_response()
                
                # Update session with gateway_id
                if self.db and self.current_session_id:
                    self.db.cursor.execute(
                        "UPDATE sessions SET gateway_id = ? WHERE id = ?",
                        (gateway_id, self.current_session_id)
                    )
                    self.db.conn.commit()
                
                try:
                    if hasattr(self.window, "label_gateway_status"):
                        status_text = f"Gateway: {gateway_id}"
                        if queue_size > 0:
                            status_text += f" (syncing {queue_size} msgs)"
                        self.window.label_gateway_status.setText(status_text)
                        self.window.label_gateway_status.setStyleSheet("color: green;")
                except Exception:
                    pass
                    
            except Exception as e:
                print(f"[HANDSHAKE] Error processing request: {e}")
            return
        
        # Handle GPS data from dedicated topic
        if msg.topic == GPS_TOPIC:
            try:
                payload = msg.payload.decode("utf-8", errors="ignore")
                print(f"🌍 GPS [{msg.topic}]: {payload}")
                
                gps_data = json.loads(payload)
                
                # Store in database
                if self.db:
                    self.db.insert_reading(gps_data)
                
                # Extract GPS coordinates
                lat = gps_data.get("latitude")
                lon = gps_data.get("longitude")
                altitude = gps_data.get("altitude")
                satellites = gps_data.get("satellites")
                gps_status = gps_data.get("status")
                
                # Update GPS label
                if lat is not None and lon is not None and gps_status == "ok":
                    try:
                        # Format: "Lat, Lon (Alt m) [Sats]"
                        gps_text = f"{lat:.5f}, {lon:.5f}"
                        if altitude is not None:
                            gps_text += f" ({altitude:.1f}m)"
                        if satellites is not None:
                            gps_text += f" [{satellites} sats]"
                        
                        if hasattr(self.window, "label_GPS_coordinates"):
                            self.window.label_GPS_coordinates.setText(gps_text)
                            self.window.label_GPS_coordinates.setStyleSheet("color: green;")
                        elif hasattr(self.window, "label_gps_value"):
                            self.window.label_gps_value.setText(gps_text)
                            self.window.label_gps_value.setStyleSheet("color: green;")
                        print(f"✓ GPS updated: {gps_text}")
                    except Exception as e:
                        print(f"GPS label update failed: {e}")
                elif gps_status == "error":
                    # No GPS fix
                    try:
                        error_msg = gps_data.get("message", "No GPS fix")
                        if hasattr(self.window, "label_GPS_coordinates"):
                            self.window.label_GPS_coordinates.setText(error_msg)
                            self.window.label_GPS_coordinates.setStyleSheet("color: orange;")
                        elif hasattr(self.window, "label_gps_value"):
                            self.window.label_gps_value.setText(error_msg)
                            self.window.label_gps_value.setStyleSheet("color: orange;")
                        print(f"⚠ GPS: {error_msg}")
                    except Exception as e:
                        print(f"GPS error display failed: {e}")
                        
            except Exception as e:
                print(f"GPS message error: {e}")
            return
        
        # Handle regular sensor data
        try:
            payload = msg.payload.decode("utf-8", errors="ignore")
            print(f"RX [{msg.topic}]: {payload}")

            data = json.loads(payload)
            
            # *** SAVE TO DATABASE ***
            if self.db:
                self.db.insert_reading(data)
            
        except Exception as e:
            print("Invalid JSON message:", e)
            return

        # Update UI elements
        msg_type = data.get("type", "").lower()

        # Temperature
        if "temp" in data:
            t = data.get("temp")
            self._set_temperature(t)
        elif "temperature" in data:
            t = data.get("temperature")
            self._set_temperature(t)
        elif msg_type == "dht11" and "temperature" in data:
            self._set_temperature(data.get("temperature"))

        # Humidity
        if "humidity" in data:
            h = data.get("humidity")
            try:
                self.window.label_humidity_value.setText(f"{h} %")
            except Exception:
                pass

        # Pressure
        if "pressure" in data or "hpa" in data:
            p = data.get("pressure", data.get("hpa"))
            try:
                self.window.label_pressure_value.setText(f"{p} hPa")
            except Exception:
                pass

        # Wind speed
        if "windspeed" in data:
            w = data.get("windspeed")
            try:
                self.window.label_windspeed_value.setText(f"{w} m/s")
            except Exception:
                pass
        elif "avg_speed" in data:
            w = data.get("avg_speed")
            try:
                self.window.label_windspeed_value.setText(f"{w:.2f} m/s")
            except Exception:
                pass

        # Wind direction
        if "direction" in data:
            dir_val = data.get("direction")
            angle = convert_cardinal_to_angle(dir_val)
            self.compass.setDirection(angle)
        elif "heading" in data:
            try:
                deg = float(data.get("heading"))
                self.compass.setDirection(deg)
            except Exception:
                pass

        # GPS (optional)
        if "latitude" in data and "longitude" in data:
            lat = data.get("latitude")
            lon = data.get("longitude")
            try:
                # Try multiple possible label names
                if hasattr(self.window, "label_GPS_coordinates"):
                    self.window.label_GPS_coordinates.setText(f"{lat:.5f}, {lon:.5f}")
                elif hasattr(self.window, "label_gps_value"):
                    self.window.label_gps_value.setText(f"{lat:.5f}, {lon:.5f}")
            except Exception as e:
                print(f"GPS label update failed: {e}")

    # ---------------- UI update helpers ----------------
    def _set_temperature(self, t):
        """Update temperature display and add to graph"""
        try:
            if isinstance(t, (int, float)):
                display = f"{t:.1f} °C"
            else:
                display = f"{t} °C"
            self.window.label_temperature_value.setText(display)
        except Exception:
            pass

        # Add to graph
        try:
            self.temp_graph.add_temperature(t)
        except Exception as e:
            print(f"Error adding temperature to graph: {e}")

    def _refresh_plots(self):
        """Refresh the temperature graph"""
        try:
            self.temp_graph.refresh()
        except Exception:
            pass

    # ---------------- run ----------------
    def run(self):
        self.window.setWindowTitle("Remote Weather Station Dashboard")
        self.window.show()
        sys.exit(self.app.exec())
    
    def __del__(self):
        """Cleanup on exit"""
        if hasattr(self, 'db') and self.db:
            self.db.close()


if __name__ == "__main__":
    dashboard = WeatherDashboard(ui_filename="UI.ui")
    dashboard.run()