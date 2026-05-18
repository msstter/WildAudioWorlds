"""Create a Windows Desktop shortcut for the Bioacoustics Rhythm Pipeline GUI.

Run this script once on a Windows machine to place a shortcut with the custom
icon on the user's Desktop:

    python GUI/create_windows_shortcut.py
"""

import os
import sys

def main():
    try:
        from win32com.client import Dispatch
    except ImportError:
        print("ERROR: pywin32 is required. Install it with:")
        print("  pip install pywin32")
        sys.exit(1)

    gui_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(gui_dir)
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")

    shortcut_path = os.path.join(desktop, "Bioacoustics Rhythm Pipeline.lnk")
    target = os.path.join(gui_dir, "launch_gui.bat")
    icon = os.path.join(gui_dir, "DesktopIcon.ico")

    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target
    shortcut.WorkingDirectory = project_dir
    shortcut.Description = "Bioacoustics Rhythm Analysis Pipeline"
    if os.path.isfile(icon):
        shortcut.IconLocation = icon
    shortcut.save()

    print(f"Desktop shortcut created: {shortcut_path}")


if __name__ == "__main__":
    main()
