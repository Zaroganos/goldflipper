from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .base import BaseChart


class CandlestickChart(BaseChart):
    """Candlestick chart implementation"""

    def validate_data(self, data: pd.DataFrame) -> None:
        """Validate OHLCV data"""
        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        if not all(col in data.columns for col in required_columns):
            raise ValueError(f"Data must contain columns: {required_columns}")
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")

    def create(self) -> None:
        """Create the base candlestick chart"""
        # Select only OHLCV columns and ensure correct data types
        plot_data = self.data[["Open", "High", "Low", "Close", "Volume"]].copy()
        plot_data = plot_data.astype({"Open": "float64", "High": "float64", "Low": "float64", "Close": "float64", "Volume": "float64"})

        try:
            # Create figure
            self.figure = plt.figure(figsize=(15, 10))

            # Create subplots with space for indicators
            gs = self.figure.add_gridspec(4, 1, height_ratios=[6, 2, 1, 1])

            # Create main price subplot
            self.axes = []
            self.axes.append(self.figure.add_subplot(gs[0]))  # Price panel
            self.axes.append(self.figure.add_subplot(gs[1]))  # Volume panel
            self.axes.append(self.figure.add_subplot(gs[2]))  # First indicator panel
            self.axes.append(self.figure.add_subplot(gs[3]))  # Second indicator panel

            # Plot candlesticks with adjusted appearance
            up = plot_data[plot_data.Close >= plot_data.Open]
            down = plot_data[plot_data.Close < plot_data.Open]

            # Calculate width based on data frequency
            time_diff = plot_data.index[1] - plot_data.index[0]
            width = time_diff.total_seconds() / (24 * 60 * 60)  # Convert to days for matplotlib
            candle_width = width * 0.8
            width * 0.2

            # Plot up candlesticks
            self.axes[0].bar(
                up.index, up.Close - up.Open, bottom=up.Open, width=candle_width, color="green", alpha=0.8, zorder=2
            )  # Higher zorder to appear above grid
            self.axes[0].vlines(up.index, up.Low, up.High, color="green", linewidth=1, zorder=1)

            # Plot down candlesticks
            self.axes[0].bar(down.index, down.Close - down.Open, bottom=down.Open, width=candle_width, color="red", alpha=0.8, zorder=2)
            self.axes[0].vlines(down.index, down.Low, down.High, color="red", linewidth=1, zorder=1)

            # Plot volume with colors matching price movement
            self.axes[1].bar(up.index, up.Volume, width=candle_width, color="green", alpha=0.5)
            self.axes[1].bar(down.index, down.Volume, width=candle_width, color="red", alpha=0.5)

            # Calculate appropriate time interval for x-axis labels
            time_diff = plot_data.index[1] - plot_data.index[0]
            minutes_diff = time_diff.total_seconds() / 60

            # Configure time formatting for intraday data
            if minutes_diff <= 1:
                interval = 5  # Show every 5 minutes for 1-min data
            elif minutes_diff <= 5:
                interval = 15  # Show every 15 minutes for 5-min data
            elif minutes_diff <= 15:
                interval = 30  # Show every 30 minutes for 15-min data
            else:
                interval = 60  # Show every hour for larger intervals

            # Get time range based on actual data
            start_time = plot_data.index[0]
            last_data_point = plot_data.index[-1]

            # Add one interval to the end to ensure we show a clean ending
            end_time = last_data_point + pd.Timedelta(minutes=interval)

            # Add padding to both sides
            padding = pd.Timedelta(minutes=interval)
            display_start = start_time - padding
            display_end = end_time + padding

            # Create time points for x-axis
            time_points = pd.date_range(start=start_time, end=end_time, freq=f"{interval}min")
            time_labels = [t.strftime("%H:%M") for t in time_points]

            # Apply formatting to all axes
            for ax in self.axes:
                # Set x-axis ticks and labels explicitly
                ax.set_xticks(time_points)
                ax.set_xticklabels(time_labels, rotation=45, ha="right")

                # Set x-axis limits with padding
                ax.set_xlim(display_start, display_end)

                # Adjust tick parameters for better visibility
                ax.tick_params(axis="x", pad=10)  # Add some padding below labels

                # Other formatting
                ax.grid(True, alpha=0.2)

                # Add borders
                for spine in ax.spines.values():
                    spine.set_visible(True)

            # Set labels
            self.axes[0].set_ylabel("Price")
            self.axes[1].set_ylabel("Volume")

            # Hide the empty indicator panels initially
            self.axes[2].set_visible(False)
            self.axes[3].set_visible(False)

            # Adjust layout with more space for x-axis labels
            self.figure.subplots_adjust(
                left=0.08,
                right=0.92,
                bottom=0.2,  # Increased bottom margin for labels
                top=0.95,
                hspace=0.3,
            )

            print("\nPlot created successfully")
            print(f"Time points: {time_points}")
            print(f"Time labels: {time_labels}")

        except Exception as e:
            print(f"\nError in plot creation: {str(e)}")
            raise

        # Force update
        self.figure.canvas.draw()

    def add_overlay(self, overlay: dict[str, Any]) -> None:
        """Add an overlay to the chart"""
        if not self.figure:
            self.create()

        # Add overlay to main price panel
        self.axes[0].plot(
            overlay["data"].index,
            overlay["data"].values,
            label=overlay["name"],
            color=overlay.get("color", "blue"),
            linewidth=1.5,  # Make lines more visible
        )

        # Add legend with better positioning
        self.axes[0].legend(loc="upper left", bbox_to_anchor=(0.05, 0.95))

        # Ensure proper display after adding overlay
        self.axes[0].autoscale_view()
        self.figure.canvas.draw()

    def add_indicator(self, indicator: dict[str, Any]) -> None:
        """Add an indicator panel"""
        if not self.figure:
            self.create()

        # Make sure the panel exists and is visible
        panel = indicator.get("panel", len(self.axes) - 1)
        if panel < len(self.axes):
            self.axes[panel].set_visible(True)
            self.axes[panel].plot(indicator["data"].index, indicator["data"].values, label=indicator["name"])
            self.axes[panel].legend()
            self.axes[panel].set_ylabel(indicator["name"])

            # Adjust spacing after adding new panel
            self.figure.tight_layout()

    def show(self) -> None:
        """Display the chart"""
        if not self.figure:
            self.create()
        plt.show()

    def save(self, filename: str) -> None:
        """Save chart to file"""
        if not self.figure:
            self.create()
        self.figure.savefig(filename)
