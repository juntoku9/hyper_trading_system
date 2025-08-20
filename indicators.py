import collections
import statistics

class BollingerBands:
    """
    Calculates Bollinger Bands (Middle, Upper, Lower) on a streaming basis.

    Maintains a fixed-size window of recent data points for SMA and Standard Deviation.
    """
    def __init__(self, period: int = 20, num_std_dev: float = 2.0):
        if not isinstance(period, int) or period <= 0:
            raise ValueError("Bollinger Bands period must be a positive integer.")
        if not isinstance(num_std_dev, (int, float)) or num_std_dev < 0:
            raise ValueError("Number of standard deviations must be non-negative.")
        if period < 2 and num_std_dev > 0: # std dev needs at least 2 points
             print("Warning: Period < 2 can lead to StatisticsError for standard deviation if num_std_dev > 0.")

        self.period = period
        self.num_std_dev = num_std_dev
        self.data_window = collections.deque(maxlen=period)
        self._middle_band = None
        self._upper_band = None
        self._lower_band = None

    def update(self, new_value: float) -> tuple[float | None, float | None, float | None]:
        if not isinstance(new_value, (int, float)):
            raise TypeError("New value must be a number.")

        # Add the new value to the window
        self.data_window.append(new_value)

        if len(self.data_window) == self.period:
            current_window = list(self.data_window)

            # Middle Band (SMA)
            self._middle_band = sum(current_window) / self.period

            # Standard Deviation
            if self.period < 2: # Can't calculate std dev with less than 2 points
                std_dev = 0.0
            else:
                std_dev = statistics.stdev(current_window)

            # Upper and Lower Bands
            self._upper_band = self._middle_band + (self.num_std_dev * std_dev)
            self._lower_band = self._middle_band - (self.num_std_dev * std_dev)
        else:
            self._middle_band = None
            self._upper_band = None
            self._lower_band = None

        return self._middle_band, self._upper_band, self._lower_band

    @property
    def bands(self) -> tuple[float | None, float | None, float | None]:
        """Returns the most recently calculated Bollinger Bands (middle, upper, lower)."""
        return self._middle_band, self._upper_band, self._lower_band

    @property
    def middle_band(self) -> float | None:
        """Returns the most recently calculated middle band (SMA)."""
        return self._middle_band

    @property
    def upper_band(self) -> float | None:
        """Returns the most recently calculated upper band."""
        return self._upper_band

    @property
    def lower_band(self) -> float | None:
        """Returns the most recently calculated lower band."""
        return self._lower_band

    @property
    def is_ready(self) -> bool:
        """Returns True if enough data has been collected to calculate bands."""
        return self._middle_band is not None

    def reset(self):
        """Resets the Bollinger Bands calculator to its initial state."""
        self.data_window.clear()
        self._middle_band = None
        self._upper_band = None
        self._lower_band = None