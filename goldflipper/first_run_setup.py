import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
import sys
import subprocess
from pathlib import Path

class FirstRunSetup:
    def __init__(self):
        # Import TkinterDnD2 for drag and drop support
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            self.root = TkinterDnD.Tk()  # Use TkinterDnD.Tk() instead of tk.Tk()
        except ImportError:
            print("TkinterDnD2 not found. Please install it using: pip install tkinterdnd2")
            sys.exit(1)
            
        self.root.title("Goldflipper First Run Setup")
        self.root.geometry("400x350")  # Made taller to accommodate new button
        
        # Center the window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Create main frame
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(expand=True, fill='both')
        
        # Welcome message
        welcome_label = tk.Label(main_frame, text="Welcome to Goldflipper!", font=('Arial', 14, 'bold'))
        welcome_label.pack(pady=(0, 20))
        
        # Shortcut creation checkbox
        self.create_shortcut_var = tk.BooleanVar(value=True)
        shortcut_check = tk.Checkbutton(main_frame, text="Create desktop shortcut", 
                                      variable=self.create_shortcut_var)
        shortcut_check.pack(pady=5)
        
        # Settings file frame
        settings_frame = tk.LabelFrame(main_frame, text="Settings Configuration", padx=10, pady=10)
        settings_frame.pack(fill='x', pady=10)
        
        # Settings file question
        settings_label = tk.Label(settings_frame, text="Do you have an existing settings.yaml file?")
        settings_label.pack(pady=5)
        
        # File selection frame
        self.file_frame = tk.Frame(settings_frame)
        self.file_frame.pack(fill='x', pady=5)
        
        # File path entry
        self.file_path = tk.StringVar()
        self.file_entry = tk.Entry(self.file_frame, textvariable=self.file_path, width=30)
        self.file_entry.pack(side='left', padx=5)
        
        # Browse button
        browse_btn = tk.Button(self.file_frame, text="Browse", command=self.browse_file)
        browse_btn.pack(side='left', padx=5)
        
        # Drag and drop label
        drop_label = tk.Label(settings_frame, text="or drag and drop your settings.yaml file here")
        drop_label.pack(pady=5)
        
        # Configure drag and drop
        self.file_entry.drop_target_register(DND_FILES)
        self.file_entry.dnd_bind('<<Drop>>', self.handle_drop)
        
        # Button frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        # Continue button
        continue_btn = tk.Button(button_frame, text="Continue", command=self.process_setup)
        continue_btn.pack(side='left', padx=5)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="", fg="blue")
        self.status_label.pack(pady=5)
        
    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select settings.yaml",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path.set(file_path)
    
    def handle_drop(self, event):
        file_path = event.data
        # Remove curly braces if present (Windows drag and drop)
        file_path = file_path.strip('{}')
        self.file_path.set(file_path)
    
    def process_setup(self):
        try:
            # Create shortcut if requested
            if self.create_shortcut_var.get():
                self.create_shortcut()
            
            # Copy settings file if provided
            settings_path = self.file_path.get()
            if settings_path:
                self.copy_settings_file(settings_path)
            
            self.status_label.config(text="Setup completed successfully!", fg="green")
            messagebox.showinfo("Success", "Setup completed successfully!")
            
            # Close the setup window
            self.root.destroy()
            
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", fg="red")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
    
    def create_shortcut(self):
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            # Get the package root directory (where goldflipper.ico and launch_goldflipper.bat are)
            package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(package_root, "goldflipper.ico")
            
            shortcut_path = os.path.join(desktop, "Goldflipper.lnk")
            target_path = os.path.join(package_root, "launch_goldflipper.bat")
            
            # Create shortcut using PowerShell with proper escaping
            ps_command = f'''
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "{target_path}"
            $Shortcut.WorkingDirectory = "{package_root}"
            $Shortcut.Description = "Launch Goldflipper Trading Application"
            $Shortcut.IconLocation = "{icon_path}"
            $Shortcut.Save()
            '''
            
            # Use subprocess instead of os.system for better error handling
            result = subprocess.run(['powershell', '-Command', ps_command], 
                                 capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Failed to create shortcut: {result.stderr}")
                
        except Exception as e:
            raise Exception(f"Error creating shortcut: {str(e)}")
    
    def copy_settings_file(self, source_path):
        # Get the config directory path
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
        target_path = os.path.join(config_dir, "settings.yaml")
        
        # Create config directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        
        # Copy the file
        shutil.copy2(source_path, target_path)
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = FirstRunSetup()
    app.run() 