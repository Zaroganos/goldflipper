import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
import sys
import subprocess
from pathlib import Path

# Import exe-aware path utilities
from goldflipper.utils.exe_utils import (
    is_frozen,
    get_settings_path,
    get_settings_template_path,
    get_config_dir,
    get_executable_dir,
    get_package_root,
    get_data_location_config_path,
    set_custom_data_directory,
)


class FirstRunSetup:
    def __init__(self):
        # Import TkinterDnD2 for drag and drop support (optional)
        # In Nuitka onefile builds, the native tkdnd library may fail to load
        self.dnd_available = False
        self.DND_FILES = None
        
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            self.DND_FILES = DND_FILES
            self.root = TkinterDnD.Tk()
            self.dnd_available = True
            print("[FirstRunSetup] TkinterDnD2 loaded successfully - drag and drop enabled")
        except ImportError as e:
            print(f"[FirstRunSetup] TkinterDnD2 not available (ImportError): {e}")
            print("[FirstRunSetup] Falling back to standard Tk (drag and drop disabled)")
            self.root = tk.Tk()
        except RuntimeError as e:
            # tkdnd native library failed to load (common in Nuitka onefile builds)
            print(f"[FirstRunSetup] TkinterDnD2 native library failed to load (RuntimeError): {e}")
            print("[FirstRunSetup] Falling back to standard Tk (drag and drop disabled)")
            self.root = tk.Tk()
        except Exception as e:
            # Catch any other unexpected errors
            print(f"[FirstRunSetup] TkinterDnD2 initialization failed ({type(e).__name__}): {e}")
            print("[FirstRunSetup] Falling back to standard Tk (drag and drop disabled)")
            self.root = tk.Tk()
        
        # Check if settings file already exists (using exe-aware paths)
        self.config_dir = str(get_config_dir())
        self.settings_path = str(get_settings_path())
        self.template_path = str(get_settings_template_path())
        self.settings_exist = os.path.exists(self.settings_path)
        
        self.root.title("Goldflipper First-run Setup")
        self.root.geometry("550x650")  # Wider and taller for better readability
        
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
        
        # Always show the full setup UI - settings existence just changes defaults
        self.show_setup_ui()
    
    def _create_data_directory_ui(self):
        """Create UI for choosing custom data directory (exe mode only)."""
        from goldflipper.utils.exe_utils import get_default_data_directory
        
        data_frame = tk.LabelFrame(self.main_frame, text="Data Directory", padx=10, pady=10)
        data_frame.pack(fill='x', pady=10)
        
        # Get default location
        default_dir = str(get_default_data_directory())
        
        # Explanation
        info_label = tk.Label(
            data_frame,
            text="Where should Goldflipper store data?\n(settings, plays, logs)",
            justify='left'
        )
        info_label.pack(pady=5)
        
        # Use default checkbox
        self.use_default_data_dir = tk.BooleanVar(value=True)
        default_check = tk.Checkbutton(
            data_frame, 
            text=f"Use default location (next to exe)",
            variable=self.use_default_data_dir,
            command=self._toggle_data_dir_entry
        )
        default_check.pack(anchor='w', pady=2)
        
        # Show default path
        default_path_label = tk.Label(
            data_frame, 
            text=f"Default: {default_dir}",
            font=('Arial', 8), 
            fg='gray'
        )
        default_path_label.pack(anchor='w', padx=20)
        
        # Custom directory selection frame
        self.data_dir_frame = tk.Frame(data_frame)
        self.data_dir_frame.pack(fill='x', pady=5)
        
        self.custom_data_dir = tk.StringVar()
        self.data_dir_entry = tk.Entry(self.data_dir_frame, textvariable=self.custom_data_dir, width=30)
        self.data_dir_entry.pack(side='left', padx=5)
        self.data_dir_entry.config(state='disabled')  # Disabled by default
        
        self.data_dir_browse_btn = tk.Button(
            self.data_dir_frame, 
            text="Browse...", 
            command=self._browse_data_directory,
            state='disabled'
        )
        self.data_dir_browse_btn.pack(side='left', padx=5)
    
    def _toggle_data_dir_entry(self):
        """Enable/disable custom data directory entry based on checkbox."""
        if self.use_default_data_dir.get():
            self.data_dir_entry.config(state='disabled')
            self.data_dir_browse_btn.config(state='disabled')
        else:
            self.data_dir_entry.config(state='normal')
            self.data_dir_browse_btn.config(state='normal')
    
    def _browse_data_directory(self):
        """Open folder browser for custom data directory."""
        dir_path = filedialog.askdirectory(
            title="Select Data Directory",
            mustexist=False
        )
        if dir_path:
            self.custom_data_dir.set(dir_path)
    
    def show_setup_ui(self):
        """Show the main setup UI - works for both new and existing settings"""
        # Clear existing widgets except welcome message
        for widget in self.main_frame.winfo_children():
            if not isinstance(widget, tk.Label) or widget.cget("text") != "Goldflipper Setup Wizard":
                widget.destroy()
        
        # Shortcut creation checkbox
        self.create_shortcut_var = tk.BooleanVar(value=True)
        shortcut_check = tk.Checkbutton(self.main_frame, text="Create Desktop shortcut", 
                                      variable=self.create_shortcut_var)
        shortcut_check.pack(pady=5)
        
        # Data directory frame (only show in frozen/exe mode)
        if is_frozen():
            self._create_data_directory_ui()
        
        # Settings file frame
        settings_frame = tk.LabelFrame(self.main_frame, text="Settings Configuration", padx=10, pady=10)
        settings_frame.pack(fill='x', pady=10)
        
        # Show current settings status
        if self.settings_exist:
            current_label = tk.Label(settings_frame, 
                                    text=f"✓ Current settings: {self.settings_path}",
                                    fg='green', font=('Arial', 9))
            current_label.pack(pady=2)
            settings_label = tk.Label(settings_frame, 
                                    text="To use a different settings file, select it below:")
        else:
            settings_label = tk.Label(settings_frame, 
                                    text="Select an existing settings file (settings.yaml) or leave empty to generate a new one.")
        settings_label.pack(pady=5)
        
        # File selection frame
        self.file_frame = tk.Frame(settings_frame)
        self.file_frame.pack(fill='x', pady=5)
        
        # File path entry
        self.file_path = tk.StringVar()
        self.file_entry = tk.Entry(self.file_frame, textvariable=self.file_path, width=30)
        self.file_entry.pack(side='left', padx=5)
        
        # Browse button
        browse_btn = tk.Button(self.file_frame, text="Browse...", command=self.browse_file)
        browse_btn.pack(side='left', padx=5)
        
        # Drag and drop (only if available)
        if self.dnd_available and self.DND_FILES:
            drop_label = tk.Label(settings_frame, text="or drag and drop your settings.yaml file here")
            drop_label.pack(pady=5)
            try:
                self.file_entry.drop_target_register(self.DND_FILES)
                self.file_entry.dnd_bind('<<Drop>>', self.handle_drop)
            except Exception as e:
                print(f"[FirstRunSetup] Failed to register drag-and-drop: {e}")
        else:
            # No drag-and-drop available - just show browse instruction
            drop_label = tk.Label(settings_frame, text="(use Browse button to select file)")
            drop_label.pack(pady=5)
        
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
            # Handle custom data directory choice (exe mode only)
            if hasattr(self, 'use_default_data_dir'):
                if not self.use_default_data_dir.get():
                    # User chose a custom directory
                    custom_dir = self.custom_data_dir.get().strip()
                    if custom_dir:
                        set_custom_data_directory(Path(custom_dir))
                        self.status_label.config(text=f"Data directory: {custom_dir}", fg="blue")
                    else:
                        # No custom dir specified, use default
                        set_custom_data_directory(None)
                else:
                    # Using default - clear any previous custom setting
                    set_custom_data_directory(None)
                
                # Re-read paths after setting data directory
                self.config_dir = str(get_config_dir())
                self.settings_path = str(get_settings_path())
            
            # Create shortcut if requested
            if hasattr(self, 'create_shortcut_var') and self.create_shortcut_var.get():
                self.create_shortcut()
            
            # Handle settings file
            if hasattr(self, 'file_path'):
                settings_path = self.file_path.get().strip()
                if settings_path:
                    # User provided a settings file - copy it (may overwrite existing)
                    self.copy_settings_file(settings_path)
                elif not self.settings_exist:
                    # No file provided AND no existing settings - create from template
                    self.create_settings_from_template()
                # If settings exist and no new file provided, keep existing (do nothing)
            
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
        
        # Ensure backup dir exists
        if not os.path.exists(backup_dir):
            return
        
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
        """Create settings.yaml from template.
        
        Uses exe-aware paths: template is bundled, settings persist next to exe.
        """
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Template file not found at {self.template_path}")
        
        # Backup existing settings if it exists
        if os.path.exists(self.settings_path):
            self.backup_existing_settings()
        
        # Create config directory if it doesn't exist (important for frozen mode)
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Copy template to settings.yaml
        shutil.copy2(self.template_path, self.settings_path)
    
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
                # CRITICAL: In Nuitka onefile mode, sys.executable points to python.exe
                # in the temp extraction directory! Use sys.argv[0] for the actual exe path.
                exe_path = sys.argv[0] if sys.argv else sys.executable
                if not os.path.isabs(exe_path):
                    exe_path = os.path.abspath(exe_path)
                target_path = exe_path
                working_dir = os.path.dirname(exe_path)
                icon_path = os.path.join(working_dir, "goldflipper.ico")
                # Fallback icon to exe itself if .ico not found
                if not os.path.exists(icon_path):
                    icon_path = sys.executable
                description = "Launch Goldflipper"
            else:
                # Running from source - shortcut points to batch file
                package_root = str(get_package_root())
                target_path = os.path.join(package_root, "launch_goldflipper.bat")
                working_dir = package_root
                icon_path = os.path.join(package_root, "goldflipper.ico")
                description = "Launch Goldflipper in Dev Mode"
            
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
                # CRITICAL: Use sys.argv[0] not sys.executable for Nuitka onefile
                exe_path = sys.argv[0] if sys.argv else sys.executable
                if not os.path.isabs(exe_path):
                    exe_path = os.path.abspath(exe_path)
                target_path = exe_path
                working_dir = os.path.dirname(exe_path)
            else:
                package_root = str(get_package_root())
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
        """Copy a user-provided settings file to the config directory.
        
        Uses exe-aware paths for destination.
        """
        # Backup existing settings if it exists
        if os.path.exists(self.settings_path):
            self.backup_existing_settings()
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Copy the file
        shutil.copy2(source_path, self.settings_path)
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = FirstRunSetup()
    app.run()
