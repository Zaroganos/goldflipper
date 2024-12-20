import os
import sys
import json
from datetime import datetime

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.logging.trade_logger import PlayLogger
from goldflipper.utils.display import TerminalDisplay as display
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

class TradeLoggerUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Goldflipper Trade Logger")
        self.root.geometry("600x400")
        self.logger = PlayLogger()
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Buttons
        ttk.Button(main_frame, text="View Web Dashboard", 
                  command=self.launch_web_dashboard).grid(row=0, column=0, pady=5)
        ttk.Button(main_frame, text="Export to Excel", 
                  command=self.export_excel).grid(row=0, column=1, pady=5)
        ttk.Button(main_frame, text="Export to CSV", 
                  command=self.export_csv).grid(row=0, column=2, pady=5)
        
        # Summary stats
        stats_frame = ttk.LabelFrame(main_frame, text="Summary Statistics", padding="5")
        stats_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        self.update_summary_stats(stats_frame)
        
        # Refresh button
        ttk.Button(main_frame, text="Refresh Data", 
                  command=lambda: self.update_summary_stats(stats_frame)).grid(row=2, column=0, columnspan=3, pady=5)

    def update_summary_stats(self, frame):
        """Update the statistics display"""
        # Clear existing stats
        for widget in frame.winfo_children():
            widget.destroy()
            
        try:
            stats_df = self.logger._create_summary_stats()
            
            # Extract values from DataFrame (getting first row since we only have one)
            total_trades = int(stats_df['total_trades'].iloc[0])
            win_rate = float(stats_df['win_rate'].iloc[0])
            total_pl = float(stats_df['total_pl'].iloc[0])
            
            # Format the statistics text
            stats_text = (
                f"Total Trades: {total_trades}\n"
                f"Win Rate: {win_rate:.2f}%\n"
                f"Total P/L: ${total_pl:.2f}"
            )
            
            ttk.Label(frame, text=stats_text).grid(row=0, column=0, padx=5, pady=5)
            
        except Exception as e:
            ttk.Label(frame, text=f"Error loading stats: {str(e)}").grid(row=0, column=0, padx=5, pady=5)

    def launch_web_dashboard(self):
        try:
            self.logger.launch_web_interface()
            webbrowser.open('http://localhost:8050')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch dashboard: {str(e)}")

    def export_excel(self):
        try:
            path = self.logger.export_to_spreadsheet(format='excel')
            messagebox.showinfo("Success", f"Excel file exported to: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export Excel: {str(e)}")

    def export_csv(self):
        try:
            path = self.logger.export_to_spreadsheet(format='csv')
            messagebox.showinfo("Success", f"CSV file exported to: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = TradeLoggerUI()
    app.logger.import_closed_plays()  # This will import all closed/expired plays
    app.run()
