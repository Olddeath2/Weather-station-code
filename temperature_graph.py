#temperature_graph.py
from collections import deque
from datetime import datetime
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates


class TemperatureGraph(FigureCanvasQTAgg):
    """
    Temperature history graph widget with automatic formatting and scaling.
    Maintains a rolling window of temperature readings with timestamps.
    """
    
    def __init__(self, parent=None, width=5, height=3, dpi=100, max_samples=300):
        """
        Initialize the temperature graph.
        
        Args:
            parent: Parent widget
            width: Figure width in inches
            height: Figure height in inches
            dpi: Dots per inch
            max_samples: Maximum number of samples to display
        """
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        
        # Data storage
        self.temp_history = deque(maxlen=max_samples)
        self.time_history = deque(maxlen=max_samples)
        
        # Configuration
        self.use_timestamps = True  # True for time-based, False for sample numbers
        self.sample_count = 0
        
        # Styling
        self.line_color = '#2E86AB'
        self.marker_color = '#A23B72'
        
        fig.tight_layout()
        
    def add_temperature(self, temp_value):
        """
        Add a new temperature reading to the graph.
        
        Args:
            temp_value: Temperature value (float or int)
        """
        try:
            fv = float(temp_value)
            self.temp_history.append(fv)
            
            if self.use_timestamps:
                self.time_history.append(datetime.now())
            else:
                self.time_history.append(self.sample_count)
                self.sample_count += 1
                
        except (ValueError, TypeError) as e:
            print(f"Invalid temperature value: {e}")
    
    def clear_history(self):
        """Clear all temperature history."""
        self.temp_history.clear()
        self.time_history.clear()
        self.sample_count = 0
        self.refresh()
    
    def set_time_mode(self, use_timestamps=True):
        """
        Switch between timestamp and sample number display.
        
        Args:
            use_timestamps: True for datetime, False for sample numbers
        """
        self.use_timestamps = use_timestamps
        # Clear and reset when switching modes
        self.clear_history()
    
    def refresh(self):
        """Refresh the plot with current data."""
        try:
            self.ax.clear()
            
            if len(self.temp_history) >= 1:
                temps = list(self.temp_history)
                times = list(self.time_history)
                
                # Plot with styling
                self.ax.plot(times, temps, 
                           color=self.line_color, 
                           linewidth=2,
                           marker='o', 
                           markersize=3, 
                           markerfacecolor=self.marker_color,
                           markeredgewidth=0,
                           label='Temperature')
                
                # Y-axis limits with smart padding
                temp_min = min(temps)
                temp_max = max(temps)
                temp_range = temp_max - temp_min
                
                if temp_range < 5:
                    padding = 2.5
                else:
                    padding = temp_range * 0.1
                
                self.ax.set_ylim(temp_min - padding, temp_max + padding)
                
                # X-axis formatting
                if self.use_timestamps and times:
                    # Format time axis
                    self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                    self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                    
                    # Rotate labels for readability
                    for label in self.ax.get_xticklabels():
                        label.set_rotation(45)
                        label.set_ha('right')
                    
                    self.ax.set_xlabel("Time", fontsize=9)
                else:
                    # Sample number mode
                    self.ax.set_xlabel("Sample #", fontsize=9)
                    
                    # Show only every Nth tick to avoid crowding
                    if len(times) > 20:
                        step = max(1, len(times) // 10)
                        tick_positions = times[::step]
                        self.ax.set_xticks(tick_positions)
                
                # Labels and title
                self.ax.set_ylabel("Temperature (°C)", fontsize=10, fontweight='bold')
                self.ax.set_title("Temperature History", fontsize=11, fontweight='bold', pad=10)
                
                # Grid for readability
                self.ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
                
                # Tick formatting
                self.ax.tick_params(labelsize=8)
                
            else:
                # No data yet
                self.ax.text(0.5, 0.5, 'Waiting for data...', 
                           horizontalalignment='center',
                           verticalalignment='center',
                           transform=self.ax.transAxes,
                           fontsize=12, 
                           color='gray')
                self.ax.set_xlim(0, 100)
                self.ax.set_ylim(0, 40)
                self.ax.set_xlabel("Time/Samples", fontsize=9)
                self.ax.set_ylabel("Temperature (°C)", fontsize=10)
            
            # Tight layout to prevent label cutoff
            self.figure.tight_layout()
            self.draw()
            
        except Exception as e:
            print(f"Graph refresh error: {e}")
    
    def get_statistics(self):
        """
        Get current statistics about the temperature data.
        
        Returns:
            dict: Dictionary with min, max, avg, current temperature
        """
        if not self.temp_history:
            return None
            
        temps = list(self.temp_history)
        return {
            'current': temps[-1],
            'min': min(temps),
            'max': max(temps),
            'avg': sum(temps) / len(temps),
            'count': len(temps)
        }