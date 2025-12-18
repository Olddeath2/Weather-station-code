# weather_database.py
import sqlite3
import json
from datetime import datetime
from pathlib import Path


class WeatherDatabase:
    """
    SQLite database for storing weather station data.
    Easy to access, query, and export.
    """
    
    def __init__(self, db_path="weather_data.db"):
        """
        Initialize database connection and create tables if needed.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Allow dict-like access
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        
        # Main sensor readings table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                temperature REAL,
                humidity REAL,
                pressure REAL,
                wind_speed REAL,
                wind_direction TEXT,
                wind_heading REAL,
                latitude REAL,
                longitude REAL,
                altitude REAL,
                satellites INTEGER,
                gps_status TEXT,
                raw_data TEXT,
                sensor_type TEXT
            )
        """)
        
        # Index for faster time-based queries
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON sensor_readings(timestamp)
        """)
        
        # Sessions table (for tracking connection sessions)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME,
                gateway_id TEXT,
                status TEXT
            )
        """)
        
        self.conn.commit()
    
    def insert_reading(self, data_dict):
        """
        Insert a sensor reading into the database.
        
        Args:
            data_dict: Dictionary containing sensor data
            
        Returns:
            int: ID of inserted row
        """
        try:
            # Extract fields
            temp = data_dict.get('temp') or data_dict.get('temperature')
            humidity = data_dict.get('humidity')
            pressure = data_dict.get('pressure') or data_dict.get('hpa')
            wind_speed = data_dict.get('windspeed') or data_dict.get('avg_speed')
            wind_direction = data_dict.get('direction')
            wind_heading = data_dict.get('heading')
            latitude = data_dict.get('latitude')
            longitude = data_dict.get('longitude')
            altitude = data_dict.get('altitude')
            satellites = data_dict.get('satellites')
            gps_status = data_dict.get('status')  # "ok" or "error"
            sensor_type = data_dict.get('type')
            
            # Store raw JSON for reference
            raw_data = json.dumps(data_dict)
            
            self.cursor.execute("""
                INSERT INTO sensor_readings 
                (temperature, humidity, pressure, wind_speed, wind_direction, 
                 wind_heading, latitude, longitude, altitude, satellites, 
                 gps_status, raw_data, sensor_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (temp, humidity, pressure, wind_speed, wind_direction,
                  wind_heading, latitude, longitude, altitude, satellites,
                  gps_status, raw_data, sensor_type))
            
            self.conn.commit()
            return self.cursor.lastrowid
            
        except Exception as e:
            print(f"Database insert error: {e}")
            self.conn.rollback()
            return None
    
    def get_recent_readings(self, limit=100):
        """
        Get most recent sensor readings.
        
        Args:
            limit: Maximum number of readings to return
            
        Returns:
            list: List of readings as dictionaries
        """
        self.cursor.execute("""
            SELECT * FROM sensor_readings 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_readings_by_timerange(self, start_time, end_time):
        """
        Get readings within a time range.
        
        Args:
            start_time: Start datetime (string or datetime object)
            end_time: End datetime (string or datetime object)
            
        Returns:
            list: List of readings as dictionaries
        """
        if isinstance(start_time, datetime):
            start_time = start_time.isoformat()
        if isinstance(end_time, datetime):
            end_time = end_time.isoformat()
        
        self.cursor.execute("""
            SELECT * FROM sensor_readings 
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """, (start_time, end_time))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_temperature_history(self, hours=24):
        """
        Get temperature readings for the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            list: List of (timestamp, temperature) tuples
        """
        self.cursor.execute("""
            SELECT timestamp, temperature 
            FROM sensor_readings 
            WHERE timestamp > datetime('now', '-' || ? || ' hours')
            AND temperature IS NOT NULL
            ORDER BY timestamp ASC
        """, (hours,))
        
        return [(row['timestamp'], row['temperature']) for row in self.cursor.fetchall()]
    
    def get_statistics(self, hours=24):
        """
        Get statistical summary of recent data.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            dict: Statistics dictionary
        """
        self.cursor.execute("""
            SELECT 
                COUNT(*) as count,
                AVG(temperature) as avg_temp,
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                AVG(humidity) as avg_humidity,
                AVG(pressure) as avg_pressure,
                AVG(wind_speed) as avg_wind_speed
            FROM sensor_readings
            WHERE timestamp > datetime('now', '-' || ? || ' hours')
        """, (hours,))
        
        row = self.cursor.fetchone()
        return dict(row) if row else {}
    
    def export_to_csv(self, output_path, start_time=None, end_time=None):
        """
        Export data to CSV file.
        
        Args:
            output_path: Path for output CSV file
            start_time: Optional start time filter
            end_time: Optional end time filter
        """
        import csv
        
        # Build query
        if start_time and end_time:
            readings = self.get_readings_by_timerange(start_time, end_time)
        else:
            readings = self.get_recent_readings(limit=10000)
        
        if not readings:
            print("No data to export")
            return
        
        # Write CSV
        with open(output_path, 'w', newline='') as csvfile:
            fieldnames = readings[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(readings)
        
        print(f"Exported {len(readings)} readings to {output_path}")
    
    def create_session(self, gateway_id=None):
        """
        Create a new connection session record.
        
        Args:
            gateway_id: Optional gateway identifier
            
        Returns:
            int: Session ID
        """
        self.cursor.execute("""
            INSERT INTO sessions (gateway_id, status)
            VALUES (?, 'active')
        """, (gateway_id,))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def close_session(self, session_id):
        """Close a session."""
        self.cursor.execute("""
            UPDATE sessions 
            SET end_time = CURRENT_TIMESTAMP, status = 'closed'
            WHERE id = ?
        """, (session_id,))
        self.conn.commit()
    
    def clear_old_data(self, days=30):
        """
        Delete data older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            int: Number of rows deleted
        """
        self.cursor.execute("""
            DELETE FROM sensor_readings 
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))
        deleted = self.cursor.rowcount
        self.conn.commit()
        return deleted
    
    def close(self):
        """Close database connection."""
        self.conn.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.conn.close()
        except:
            pass