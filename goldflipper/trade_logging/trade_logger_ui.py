import os
import sys
import pandas as pd

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.trade_logging.trade_logger import PlayLogger
from goldflipper.utils.display import TerminalDisplay as display
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess

class TradeLoggerUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Goldflipper Trade Log")
        self.root.geometry("600x450")  # Compact size after removing export history tab
        
        # Logger options
        self.enable_backfill = tk.BooleanVar(value=True)
        self.include_all_folders = tk.BooleanVar(value=False)
        self.logger = PlayLogger(enable_backfill=self.enable_backfill.get())
        
        # Export options
        self.save_to_desktop = tk.BooleanVar(value=True)
        self.export_csv = tk.BooleanVar(value=True)
        self.export_excel = tk.BooleanVar(value=True)
        
        # Strategy filter for multi-strategy support
        self.strategy_filter = tk.StringVar(value="All")
        self.available_strategies = ["All"]  # Will be populated from data
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Buttons frame - simplified (removed web dashboard which doesn't exist)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        button_frame.columnconfigure(1, weight=1)  # Make the last column expandable
        
        ttk.Button(button_frame, text="Export", 
                  command=self.export_data).grid(row=0, column=0, pady=5, padx=2)
        ttk.Button(button_frame, text="Open Export Folder", 
                  command=self.open_export_folder).grid(row=0, column=1, pady=5, padx=2, sticky=tk.W)
        
        # Export options frame
        options_frame = ttk.LabelFrame(main_frame, text="Export Options", padding="5")
        options_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Format options
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(format_frame, text="Format:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(format_frame, text="CSV", 
                       variable=self.export_csv).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(format_frame, text="Excel", 
                       variable=self.export_excel).pack(side=tk.LEFT, padx=10)
        
        # Desktop option
        desktop_frame = ttk.Frame(options_frame)
        desktop_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(desktop_frame, text="Save to Desktop", 
                       variable=self.save_to_desktop).pack(side=tk.LEFT, padx=(0, 10))
        
        # Data backfill option
        backfill_frame = ttk.Frame(options_frame)
        backfill_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(backfill_frame, text="Enable Data Backfill (fetch missing Greeks from API)", 
                       variable=self.enable_backfill,
                       command=self.on_backfill_changed).pack(side=tk.LEFT, padx=(0, 10))

        # Include all folders option
        scope_frame = ttk.Frame(options_frame)
        scope_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(scope_frame, text="Include ALL folders (except Old)", 
                       variable=self.include_all_folders).pack(side=tk.LEFT, padx=(0, 10))
        
        # Strategy filter dropdown (multi-strategy support)
        filter_frame = ttk.Frame(options_frame)
        filter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(filter_frame, text="Strategy Filter:").pack(side=tk.LEFT, padx=(0, 10))
        self.strategy_combo = ttk.Combobox(
            filter_frame, 
            textvariable=self.strategy_filter,
            values=self.available_strategies,
            state="readonly",
            width=20
        )
        self.strategy_combo.pack(side=tk.LEFT, padx=5)
        self.strategy_combo.bind("<<ComboboxSelected>>", self.on_strategy_filter_changed)
        
        # Update available strategies from data
        self._update_strategy_list()
        
        # Summary stats
        stats_frame = ttk.LabelFrame(main_frame, text="Summary Statistics", padding="5")
        stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        self.update_summary_stats(stats_frame)
        
        # Refresh button
        ttk.Button(main_frame, text="Refresh Data", 
                  command=lambda: self.refresh_all_data(stats_frame)).grid(row=3, column=0, pady=5)

    def on_backfill_changed(self):
        """Handle backfill option change - recreate logger with new setting"""
        try:
            # Recreate the logger with the new backfill setting
            self.logger = PlayLogger(
                base_directory=self.logger.base_directory,
                save_to_desktop=self.logger.save_to_desktop,
                enable_backfill=self.enable_backfill.get()
            )
            
            if self.enable_backfill.get():
                messagebox.showinfo("Backfill Enabled", 
                    "Data backfill is now enabled. The next refresh will attempt to fetch missing Greeks data from the API.")
            else:
                messagebox.showinfo("Backfill Disabled", 
                    "Data backfill is now disabled. Future refreshes will not fetch missing data from the API.")
                    
        except Exception as e:
            messagebox.showerror("Logger Error", f"Failed to update logger settings: {str(e)}")

    def _update_strategy_list(self):
        """Update the strategy dropdown with strategies from the current data."""
        try:
            strategies = self.logger.get_unique_strategies()
            self.available_strategies = ["All"] + strategies
            self.strategy_combo['values'] = self.available_strategies
        except Exception as e:
            # If no data or error, just keep "All"
            self.available_strategies = ["All"]
            self.strategy_combo['values'] = self.available_strategies

    def on_strategy_filter_changed(self, event=None):
        """Handle strategy filter selection change."""
        # Find the stats frame and update it
        for child in self.root.winfo_children():
            for subchild in child.winfo_children():
                if isinstance(subchild, ttk.LabelFrame) and "Statistics" in str(subchild.cget("text")):
                    self.update_summary_stats(subchild)
                    break

    def refresh_all_data(self, stats_frame):
        """Refresh all data by re-importing plays and updating statistics"""
        try:
            # Show a status message
            status_label = ttk.Label(stats_frame, text="Refreshing data...")
            status_label.grid(row=0, column=0, padx=10, pady=5)
            self.root.update()  # Force UI update
            
            # Ensure logger has current settings
            if self.logger.enable_backfill != self.enable_backfill.get():
                self.logger = PlayLogger(
                    base_directory=self.logger.base_directory,
                    save_to_desktop=self.logger.save_to_desktop,
                    enable_backfill=self.enable_backfill.get()
                )
            
            # Re-import plays based on scope selection
            if self.include_all_folders.get():
                imported_count = self.logger.import_all_plays()
            else:
                imported_count = self.logger.import_closed_plays()
            
            # Remove status message
            status_label.destroy()
            
            # Update the strategy dropdown with new data
            self._update_strategy_list()
            
            # Update the summary statistics
            self.update_summary_stats(stats_frame)
            
            # Show success message
            backfill_status = " (with data backfill)" if self.logger.enable_backfill else ""
            scope_status = " from ALL folders" if self.include_all_folders.get() else " from closed/expired"
            messagebox.showinfo("Refresh Complete", f"Successfully refreshed data{backfill_status}{scope_status}.\n{imported_count} plays imported.")
            
        except Exception as e:
            # Remove status message if it exists
            try:
                status_label.destroy()
            except:
                pass
            messagebox.showerror("Refresh Error", f"Failed to refresh data: {str(e)}")

    def update_summary_stats(self, frame):
        """Update the statistics display with optional strategy filter."""
        # Clear existing stats
        for widget in frame.winfo_children():
            widget.destroy()
            
        try:
            # Get current strategy filter
            strategy_filter = self.strategy_filter.get()
            
            # Get summary stats (filtered by strategy if applicable)
            stats_df = self.logger._create_summary_stats(strategy_filter=strategy_filter)
            
            # Show filter status in row 0
            filter_text = f"Strategy: {strategy_filter}" if strategy_filter != "All" else "All Strategies"
            ttk.Label(frame, text=filter_text, font=('', 9, 'italic')).grid(row=0, column=0, columnspan=4, padx=10, pady=2, sticky=tk.W)
            
            # Display stats in a grid (shifted to row 1 and 2)
            ttk.Label(frame, text="Total Trades:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
            ttk.Label(frame, text=str(stats_df['total_trades'].iloc[0])).grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
            
            ttk.Label(frame, text="Winning Trades:").grid(row=1, column=2, padx=10, pady=5, sticky=tk.W)
            ttk.Label(frame, text=str(stats_df['winning_trades'].iloc[0])).grid(row=1, column=3, padx=10, pady=5, sticky=tk.W)
            
            ttk.Label(frame, text="Win Rate:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
            ttk.Label(frame, text=f"{stats_df['win_rate'].iloc[0]:.2f}%").grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)
            
            ttk.Label(frame, text="Total P/L:").grid(row=2, column=2, padx=10, pady=5, sticky=tk.W)
            pl_value = stats_df['total_pl'].iloc[0]
            pl_color = "green" if pl_value > 0 else "red" if pl_value < 0 else "black"
            pl_label = ttk.Label(frame, text=f"${pl_value:.2f}", foreground=pl_color)
            pl_label.grid(row=2, column=3, padx=10, pady=5, sticky=tk.W)
            
        except Exception as e:
            ttk.Label(frame, text=f"Error loading stats: {str(e)}").grid(row=0, column=0, padx=10, pady=5)

    def open_export_folder(self):
        """Open the export logs folder in file explorer"""
        try:
            log_dir = self.logger.log_directory
            if os.path.exists(log_dir):
                self._open_path(log_dir)
            else:
                messagebox.showinfo("Info", f"Export folder does not exist yet:\n{log_dir}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open export folder: {str(e)}")

    def _open_path(self, path):
        """Open a file or directory with the default application"""
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', path])
            else:  # Linux
                subprocess.call(['xdg-open', path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open: {str(e)}")
        
    def open_file(self, file_path):
        """Open a file with the default application"""
        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', file_path])
            else:  # Linux
                subprocess.call(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")
            
    def open_directory(self, dir_path):
        """Open a directory in the file explorer"""
        self._open_path(dir_path)

    def export_data(self):
        """Export data based on selected format options"""
        try:
            # Check if at least one format is selected
            if not self.export_csv.get() and not self.export_excel.get():
                messagebox.showwarning("Export Warning", "Please select at least one export format (CSV or Excel).")
                return
                
            # Update the logger's save_to_desktop setting
            self.logger.save_to_desktop = self.save_to_desktop.get()
            
            # Determine which format to use
            if self.export_csv.get() and self.export_excel.get():
                format_option = 'both'
            elif self.export_csv.get():
                format_option = 'csv'
            else:  # Excel only
                format_option = 'excel'
            
            # Export the data
            result = self.logger.export_to_spreadsheet(format=format_option)
            
            # Build success message
            message = "Files exported to:\n"
            
            if format_option in ['csv', 'both'] and result.get('csv_file'):
                message += f"CSV: {result['csv_file']}\n"
                
            if format_option in ['excel', 'both'] and result.get('excel_file'):
                message += f"Excel: {result['excel_file']}\n"
            
            # Add desktop paths if applicable
            desktop_files = []
            if self.save_to_desktop.get():
                if format_option in ['csv', 'both'] and result.get('csv_desktop_file'):
                    desktop_files.append(f"CSV: {result['csv_desktop_file']}")
                    
                if format_option in ['excel', 'both'] and result.get('excel_desktop_file'):
                    desktop_files.append(f"Excel: {result['excel_desktop_file']}")
            
            if desktop_files:
                message += "\nCopies have been saved to your Desktop:\n"
                message += "\n".join(desktop_files)
                
            messagebox.showinfo("Export Successful", message)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export files: {str(e)}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = TradeLoggerUI()
    # On startup, default to closed/expired only (checkbox is off by default)
    app.logger.import_closed_plays()
    app.run()
