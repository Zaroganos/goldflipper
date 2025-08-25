import os
import sys
import json
from datetime import datetime
import pandas as pd

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from goldflipper.logging.trade_logger import PlayLogger
from goldflipper.utils.display import TerminalDisplay as display
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import subprocess

class TradeLoggerUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Goldflipper Trade Logger")
        self.root.geometry("800x500")  # Increased size to accommodate new features
        self.logger = PlayLogger()
        
        # Export options
        self.save_to_desktop = tk.BooleanVar(value=True)
        self.export_csv = tk.BooleanVar(value=True)
        self.export_excel = tk.BooleanVar(value=True)
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        button_frame.columnconfigure(2, weight=1)  # Make the last column expandable
        
        ttk.Button(button_frame, text="View Web Dashboard", 
                  command=self.launch_web_dashboard).grid(row=0, column=0, pady=5, padx=2)
        ttk.Button(button_frame, text="Export", 
                  command=self.export_data).grid(row=0, column=1, pady=5, padx=2)
        ttk.Button(button_frame, text="View Export History", 
                  command=self.show_export_history).grid(row=0, column=2, pady=5, padx=2)
        
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
        
        # Summary stats
        stats_frame = ttk.LabelFrame(main_frame, text="Summary Statistics", padding="5")
        stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        self.update_summary_stats(stats_frame)
        
        # Create a notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=3, column=0, sticky=(tk.N, tk.S, tk.E, tk.W), pady=5)
        
        # Tab for history
        self.history_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(self.history_frame, text="Export History")
        
        # Refresh button
        ttk.Button(main_frame, text="Refresh Data", 
                  command=lambda: self.refresh_all_data(stats_frame)).grid(row=4, column=0, pady=5)

    def refresh_all_data(self, stats_frame):
        """Refresh all data by re-importing plays and updating statistics"""
        try:
            # Show a status message
            status_label = ttk.Label(stats_frame, text="Refreshing data...")
            status_label.grid(row=0, column=0, padx=10, pady=5)
            self.root.update()  # Force UI update
            
            # Re-import all closed and expired plays
            imported_count = self.logger.import_closed_plays()
            
            # Remove status message
            status_label.destroy()
            
            # Update the summary statistics
            self.update_summary_stats(stats_frame)
            
            # Show success message
            messagebox.showinfo("Refresh Complete", f"Successfully refreshed data.\n{imported_count} plays imported.")
            
        except Exception as e:
            # Remove status message if it exists
            try:
                status_label.destroy()
            except:
                pass
            messagebox.showerror("Refresh Error", f"Failed to refresh data: {str(e)}")

    def update_summary_stats(self, frame):
        """Update the statistics display"""
        # Clear existing stats
        for widget in frame.winfo_children():
            widget.destroy()
            
        try:
            # Get summary stats
            stats_df = self.logger._create_summary_stats()
            
            # Display stats in a grid
            ttk.Label(frame, text="Total Trades:").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
            ttk.Label(frame, text=str(stats_df['total_trades'].iloc[0])).grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
            
            ttk.Label(frame, text="Winning Trades:").grid(row=0, column=2, padx=10, pady=5, sticky=tk.W)
            ttk.Label(frame, text=str(stats_df['winning_trades'].iloc[0])).grid(row=0, column=3, padx=10, pady=5, sticky=tk.W)
            
            ttk.Label(frame, text="Win Rate:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
            ttk.Label(frame, text=f"{stats_df['win_rate'].iloc[0]:.2f}%").grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
            
            ttk.Label(frame, text="Total P/L:").grid(row=1, column=2, padx=10, pady=5, sticky=tk.W)
            pl_value = stats_df['total_pl'].iloc[0]
            pl_color = "green" if pl_value > 0 else "red" if pl_value < 0 else "black"
            pl_label = ttk.Label(frame, text=f"${pl_value:.2f}", foreground=pl_color)
            pl_label.grid(row=1, column=3, padx=10, pady=5, sticky=tk.W)
            
        except Exception as e:
            ttk.Label(frame, text=f"Error loading stats: {str(e)}").grid(row=0, column=0, padx=10, pady=5)

    def show_export_history(self):
        """Show the export history in the history tab"""
        # Clear existing content
        for widget in self.history_frame.winfo_children():
            widget.destroy()
            
        # Create a frame for the treeview
        tree_frame = ttk.Frame(self.history_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create treeview
        columns = ("Date", "Time", "CSV", "Excel", "Directory")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", yscrollcommand=scrollbar.set)
        
        # Configure scrollbar
        scrollbar.config(command=tree.yview)
        
        # Set column headings
        tree.heading("Date", text="Date")
        tree.heading("Time", text="Time")
        tree.heading("CSV", text="CSV")
        tree.heading("Excel", text="Excel")
        tree.heading("Directory", text="Directory")
        
        # Set column widths
        tree.column("Date", width=100)
        tree.column("Time", width=100)
        tree.column("CSV", width=50)
        tree.column("Excel", width=50)
        tree.column("Directory", width=300)
        
        # Get export history
        exports = self.logger.get_export_history()
        
        # Add data to treeview
        for export in exports:
            date_str = export["timestamp"].strftime("%Y-%m-%d")
            time_str = export["timestamp"].strftime("%H:%M:%S")
            csv_str = "✓" if export["csv_exists"] else "✗"
            excel_str = "✓" if export["excel_exists"] else "✗"
            dir_str = export["directory"]
            
            tree.insert("", tk.END, values=(date_str, time_str, csv_str, excel_str, dir_str))
            
        tree.pack(fill=tk.BOTH, expand=True)
        
        # Add context menu
        self.create_context_menu(tree, exports)
        
        # Select the history tab
        self.notebook.select(self.history_frame)
        
    def create_context_menu(self, tree, exports):
        """Create right-click context menu for the export history"""
        context_menu = tk.Menu(tree, tearoff=0)
        
        def open_csv():
            selected = tree.selection()
            if selected:
                index = tree.index(selected[0])
                if index < len(exports) and exports[index]["csv_exists"]:
                    self.open_file(exports[index]["csv_path"])
                    
        def open_excel():
            selected = tree.selection()
            if selected:
                index = tree.index(selected[0])
                if index < len(exports) and exports[index]["excel_exists"]:
                    self.open_file(exports[index]["excel_path"])
                    
        def open_directory():
            selected = tree.selection()
            if selected:
                index = tree.index(selected[0])
                if index < len(exports):
                    self.open_directory(exports[index]["directory"])
        
        context_menu.add_command(label="Open CSV", command=open_csv)
        context_menu.add_command(label="Open Excel", command=open_excel)
        context_menu.add_command(label="Open Directory", command=open_directory)
        
        def show_context_menu(event):
            # Select row under mouse
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                context_menu.post(event.x_root, event.y_root)
                
        tree.bind("<Button-3>", show_context_menu)  # Right-click
        
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
        try:
            if sys.platform == 'win32':
                os.startfile(dir_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', dir_path])
            else:  # Linux
                subprocess.call(['xdg-open', dir_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open directory: {str(e)}")

    def launch_web_dashboard(self):
        try:
            self.logger.launch_web_interface()
            webbrowser.open('http://localhost:8050')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch dashboard: {str(e)}")

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
            
            # Refresh the export history if it's visible
            if hasattr(self, 'history_frame') and self.notebook.index(self.notebook.select()) == 0:
                self.show_export_history()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export files: {str(e)}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = TradeLoggerUI()
    app.logger.import_closed_plays()  # This will import all closed/expired plays
    app.run()
