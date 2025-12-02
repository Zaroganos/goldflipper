import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
import sys
import subprocess
from pathlib import Path

# Exe detection utility
def is_frozen() -> bool:
    """Check if running from compiled executable."""
    return getattr(sys, 'frozen', False)

class FirstRunSetup:
    def __init__(self):
        # Import TkinterDnD2 for drag and drop support
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            self.DND_FILES = DND_FILES  # Store for later use
            self.root = TkinterDnD.Tk()  # Use TkinterDnD.Tk() instead of tk.Tk()
        except ImportError:
            print("TkinterDnD2 not found. Please install it using: uv pip install tkinterdnd2")
            sys.exit(1)
        
        # Check if settings file already exists
        self.config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
        self.settings_path = os.path.join(self.config_dir, "settings.yaml")
        self.settings_exist = os.path.exists(self.settings_path)
        
        self.root.title("Goldflipper First-run Setup")
        self.root.geometry("400x400")  # Made taller to accommodate new options
        
        # Center the window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Create main frame
        self.main_frame = tk.Frame(self.root, padx=20, pady=20)
        self.main_frame.pack(expand=True, fill='both')
        
        # Welcome message
        welcome_label = tk.Label(self.main_frame, text="Goldflipper Setup Wizard", font=('Arial', 14, 'bold'))
        welcome_label.pack(pady=(0, 20))
        
        # If settings exist, show choice dialog first
        if self.settings_exist:
            self.show_existing_settings_choice()
        else:
            self.show_new_setup_ui()
    
    def show_existing_settings_choice(self):
        """Show dialog when settings file already exists"""
        choice_frame = tk.LabelFrame(self.main_frame, text="Settings File Detected", padx=10, pady=10)
        choice_frame.pack(fill='x', pady=10)
        
        info_label = tk.Label(choice_frame, 
                             text=f"Found existing settings file:\n{self.settings_path}\n\nWhat would you like to do?",
                             justify='left')
        info_label.pack(pady=10)
        
        button_frame = tk.Frame(choice_frame)
        button_frame.pack(pady=10)
        
        use_existing_btn = tk.Button(button_frame, text="Use Existing Settings Profile", 
                                    command=self.use_existing_settings, width=20)
        use_existing_btn.pack(side='left', padx=5)
        
        create_new_btn = tk.Button(button_frame, text="Create New Settings Profile", 
                                  command=self.show_new_setup_ui, width=20)
        create_new_btn.pack(side='left', padx=5)
    
    def use_existing_settings(self):
        """User chose to use existing settings - just handle shortcut and finish"""
        self.show_shortcut_option()
    
    def show_new_setup_ui(self):
        """Show UI for new settings setup"""
        # Clear existing widgets except welcome message
        for widget in self.main_frame.winfo_children():
            if not isinstance(widget, tk.Label) or widget.cget("text") != "Welcome to Goldflipper!":
                widget.destroy()
        
        # Shortcut creation checkbox
        self.create_shortcut_var = tk.BooleanVar(value=True)
        shortcut_check = tk.Checkbutton(self.main_frame, text="Create desktop shortcut", 
                                      variable=self.create_shortcut_var)
        shortcut_check.pack(pady=5)
        
        # Settings file frame
        settings_frame = tk.LabelFrame(self.main_frame, text="Settings Configuration", padx=10, pady=10)
        settings_frame.pack(fill='x', pady=10)
        
        # Settings file question
        if self.settings_exist:
            settings_label = tk.Label(settings_frame, 
                                    text="Select a new settings file to use (settings.yaml)")
        else:
            settings_label = tk.Label(settings_frame, 
                                    text="Do you have an existing settings file? (settings.yaml)")
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
        self.file_entry.drop_target_register(self.DND_FILES)
        self.file_entry.dnd_bind('<<Drop>>', self.handle_drop)
        
        # Note about creating from template
        note_label = tk.Label(settings_frame, 
                             text="(Leave empty to create from template)", 
                             font=('Arial', 8), fg='gray')
        note_label.pack(pady=2)
        
        # Button frame
        button_frame = tk.Frame(self.main_frame)
        button_frame.pack(pady=20)
        
        # Continue button
        continue_btn = tk.Button(button_frame, text="Continue", command=self.process_setup)
        continue_btn.pack(side='left', padx=5)
        
        # Status label
        self.status_label = tk.Label(self.main_frame, text="", fg="blue")
        self.status_label.pack(pady=5)
    
    def show_shortcut_option(self):
        """Show only shortcut option when using existing settings"""
        # Clear existing widgets except welcome message
        for widget in self.main_frame.winfo_children():
            if not isinstance(widget, tk.Label) or widget.cget("text") != "Welcome to Goldflipper!":
                widget.destroy()
        
        info_label = tk.Label(self.main_frame, 
                             text="Using existing settings file.\nYou can create a desktop shortcut below.",
                             justify='center')
        info_label.pack(pady=10)
        
        # Shortcut creation checkbox
        self.create_shortcut_var = tk.BooleanVar(value=True)
        shortcut_check = tk.Checkbutton(self.main_frame, text="Create desktop shortcut", 
                                      variable=self.create_shortcut_var)
        shortcut_check.pack(pady=10)
        
        # Button frame
        button_frame = tk.Frame(self.main_frame)
        button_frame.pack(pady=20)
        
        # Continue button
        continue_btn = tk.Button(button_frame, text="Continue", command=self.process_setup)
        continue_btn.pack(side='left', padx=5)
        
        # Status label
        self.status_label = tk.Label(self.main_frame, text="", fg="blue")
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
            if hasattr(self, 'create_shortcut_var') and self.create_shortcut_var.get():
                self.create_shortcut()
            
            # Handle settings file
            if hasattr(self, 'file_path'):
                settings_path = self.file_path.get().strip()
                if settings_path:
                    # User provided a settings file - copy it (may overwrite existing)
                    self.copy_settings_file(settings_path)
                else:
                    # No file provided - create from template
                    # This will overwrite existing settings if they exist
                    self.create_settings_from_template()
            # If using existing settings (no file_path attribute), no action needed
            
            self.status_label.config(text="Setup completed successfully!", fg="green")
            messagebox.showinfo("Success", "Setup completed successfully!")
            
            # Close the setup window
            self.root.destroy()
            
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", fg="red")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
    
    def backup_existing_settings(self):
        """Backup existing settings.yaml by renaming it to settings.yaml.oldX"""
        if not os.path.exists(self.settings_path):
            return  # No existing file to backup
        
        # Find the highest existing backup number
        backup_dir = self.config_dir
        max_backup_num = 0
        
        # Look for existing backup files
        for filename in os.listdir(backup_dir):
            if filename.startswith("settings.yaml.old"):
                try:
                    # Extract the number after "settings.yaml.old"
                    num_str = filename.replace("settings.yaml.old", "")
                    if num_str.isdigit():
                        max_backup_num = max(max_backup_num, int(num_str))
                except (ValueError, AttributeError):
                    continue
        
        # Increment for the new backup
        new_backup_num = max_backup_num + 1
        backup_path = os.path.join(backup_dir, f"settings.yaml.old{new_backup_num}")
        
        # Rename existing settings to backup
        shutil.move(self.settings_path, backup_path)
    
    def create_settings_from_template(self):
        """Create settings.yaml from template"""
        template_path = os.path.join(self.config_dir, "settings_template.yaml")
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found at {template_path}")
        
        # Backup existing settings if it exists
        if os.path.exists(self.settings_path):
            self.backup_existing_settings()
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Copy template to settings.yaml
        shutil.copy2(template_path, self.settings_path)
    
    def create_shortcut(self):
        try:
            # Get desktop path using Windows shell folders (more reliable)
            import winreg
            try:
                # Try to get Desktop path from registry
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
                )
                desktop = winreg.QueryValueEx(key, "Desktop")[0]
                winreg.CloseKey(key)
            except (OSError, FileNotFoundError):
                # Fallback to user profile Desktop
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            
            # Ensure desktop directory exists
            if not os.path.exists(desktop):
                os.makedirs(desktop, exist_ok=True)
            
            # Determine target based on exe vs source mode
            if is_frozen():
                # Running from compiled exe - shortcut points to the exe
                target_path = sys.executable
                working_dir = os.path.dirname(sys.executable)
                icon_path = os.path.join(working_dir, "goldflipper.ico")
                # Fallback icon to exe itself if .ico not found
                if not os.path.exists(icon_path):
                    icon_path = sys.executable
                description = "Launch Goldflipper"
            else:
                # Running from source - shortcut points to batch file
                package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                target_path = os.path.join(package_root, "launch_goldflipper.bat")
                working_dir = package_root
                icon_path = os.path.join(package_root, "goldflipper.ico")
                description = "Launch Goldflipper (Dev Mode)"
            
            shortcut_path = os.path.join(desktop, "Goldflipper.lnk")
            
            # Escape backslashes for PowerShell (double them)
            desktop_escaped = desktop.replace("\\", "\\\\")
            shortcut_path_escaped = shortcut_path.replace("\\", "\\\\")
            target_path_escaped = target_path.replace("\\", "\\\\")
            working_dir_escaped = working_dir.replace("\\", "\\\\")
            icon_path_escaped = icon_path.replace("\\", "\\\\")
            
            # Create shortcut using PowerShell with proper escaping
            ps_command = f'''
$desktop = "{desktop_escaped}"
$shortcutPath = "{shortcut_path_escaped}"
$targetPath = "{target_path_escaped}"
$workingDir = "{working_dir_escaped}"
$iconPath = "{icon_path_escaped}"

if (-not (Test-Path $desktop)) {{
    New-Item -ItemType Directory -Path $desktop -Force | Out-Null
}}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $targetPath
$Shortcut.WorkingDirectory = $workingDir
$Shortcut.Description = "{description}"
if (Test-Path $iconPath) {{
    $Shortcut.IconLocation = $iconPath
}}
$Shortcut.Save()
'''
            
            # Use subprocess with explicit pipes (capture_output can fail in GUI contexts)
            # Also hide the PowerShell window with CREATE_NO_WINDOW flag
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                raise Exception(f"Failed to create shortcut: {error_msg}")
                
        except ImportError:
            # winreg not available (shouldn't happen on Windows, but handle gracefully)
            # Fallback to simpler method
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop):
                os.makedirs(desktop, exist_ok=True)
            
            if is_frozen():
                target_path = sys.executable
                working_dir = os.path.dirname(sys.executable)
            else:
                package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                target_path = os.path.join(package_root, "launch_goldflipper.bat")
                working_dir = package_root
            
            shortcut_path = os.path.join(desktop, "Goldflipper.lnk")
            
            # Use simpler PowerShell command with raw strings
            ps_command = f'$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); $Shortcut.TargetPath = "{target_path}"; $Shortcut.WorkingDirectory = "{working_dir}"; $Shortcut.Description = "Launch Goldflipper"; $Shortcut.Save()'
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                raise Exception(f"Failed to create shortcut: {error_msg}")
                
        except Exception as e:
            raise Exception(f"Error creating shortcut: {str(e)}")
    
    def copy_settings_file(self, source_path):
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
        target_path = os.path.join(config_dir, "settings.yaml")
        
        # Backup existing settings if it exists
        if os.path.exists(target_path):
            self.backup_existing_settings()
        
        # Create config directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        
        # Copy the file
        shutil.copy2(source_path, target_path)
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = FirstRunSetup()
    app.run() 