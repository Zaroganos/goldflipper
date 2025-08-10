import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

ENV_BAT_RELATIVE = Path(__file__).resolve().parents[2] / '.env.bat'

def write_env_bat(data_dir: Path) -> None:
    data_dir_str = str(data_dir)
    lines = [
        "@echo off\n",
        "rem Goldflipper environment configuration\n",
        "rem This file is loaded by launch scripts to set environment variables.\n",
        f"set \"GOLDFLIPPER_DATA_DIR={data_dir_str}\"\n",
    ]
    ENV_BAT_RELATIVE.write_text(''.join(lines), encoding='utf-8')

def ensure_dirs(base: Path) -> None:
    (base / 'db').mkdir(parents=True, exist_ok=True)
    (base / 'db' / 'backups').mkdir(parents=True, exist_ok=True)
    (base / 'db' / 'temp').mkdir(parents=True, exist_ok=True)

def main():
    root = tk.Tk()
    root.title('Goldflipper First-Run Database Setup')
    root.geometry('520x220')

    choice = tk.StringVar(value='new')

    tk.Label(root, text='No database detected. Choose an option:').pack(pady=10)
    tk.Radiobutton(root, text='Create new profile (new database)', variable=choice, value='new').pack(anchor='w', padx=20)
    tk.Radiobutton(root, text='Select existing data directory', variable=choice, value='existing').pack(anchor='w', padx=20)

    path_var = tk.StringVar()
    frame = tk.Frame(root)
    frame.pack(fill='x', padx=20, pady=10)
    tk.Entry(frame, textvariable=path_var).pack(side='left', fill='x', expand=True)

    def browse():
        if choice.get() == 'new':
            p = filedialog.askdirectory(title='Choose base directory for new Goldflipper data')
        else:
            p = filedialog.askdirectory(title='Select existing Goldflipper data directory (contains db folder)')
        if p:
            path_var.set(p)

    tk.Button(frame, text='Browse', command=browse).pack(side='left', padx=6)

    def proceed():
        path = path_var.get().strip()
        if not path:
            messagebox.showerror('Error', 'Please select a directory.')
            return
        base = Path(path)
        if choice.get() == 'existing':
            dbf = base / 'db' / 'goldflipper.db'
            if not dbf.exists():
                messagebox.showerror('Error', f'Expected database at {dbf} not found.')
                return
        else:
            ensure_dirs(base)
        try:
            write_env_bat(base)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to write env file: {e}')
            return
        messagebox.showinfo('Success', 'Configuration saved. You can relaunch now.')
        root.destroy()

    tk.Button(root, text='Continue', command=proceed).pack(pady=10)
    root.mainloop()

if __name__ == '__main__':
    main()


