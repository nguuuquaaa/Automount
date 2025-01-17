import pystray
from PIL import Image
import subprocess
import threading
import json
import signal
import os
import contextlib
from datetime import datetime
import ctypes

#=============================================================================================================================#

class HDD:
    def __init__(self, *, hostname: str, mount_dir: str, drive_letter: str, volume_name: str = "HDD", cache_dir: str):
        self.hostname = hostname
        self.mount_dir = mount_dir
        self.drive_letter = drive_letter
        self.volume_name = volume_name
        self.cache_dir = cache_dir
        self.process = None
        self.thread = None
        self._lock = threading.Lock()

    def log_to_stdout(self):
        while self.process:
            line = self.process.stdout.readline().decode("utf-8")
            if line:
                print(line)
            else:
                return

    def mount(self):
        with self._lock:
            if self.process is None:
                self.process = subprocess.Popen(
                    [
                        "C:\\bin\\rclone",
                        "mount", f"{self.hostname}:{self.mount_dir}", f"{self.drive_letter}:",
                        "--volname", self.volume_name,
                        "--vfs-cache-mode", "writes",
                        "--cache-dir", f"{self.cache_dir}\\{self.mount_dir}",
                        "--file-perms", "0777",
                        "--dir-perms", "0777",
                        "--no-console"
                    ],
                    stdin = subprocess.PIPE,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.STDOUT,
                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                )
                threading.Thread(target = self.log_to_stdout).start()

    def is_mounted(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def unmount(self):
        with self._lock:
            if not self.is_mounted():
                return 1

            os.kill(self.process.pid, signal.CTRL_BREAK_EVENT)
            self.process.wait()
            self.process = None
            return 0

    def current_label(self, icon):
        with self._lock:
            if self.is_mounted():
                return f"\u2796 Unmount {self.volume_name}"
            else:
                return f"\u2795 Mount {self.volume_name}"

    def callback(self, icon, item: str):
        if self.is_mounted():
            self.unmount()
        else:
            self.mount()

#=============================================================================================================================#

def mount_all(all_hdds: list[HDD]):
    for hdd in all_hdds:
        hdd.mount()

def unmount_all(all_hdds: list[HDD]):
    for hdd in all_hdds:
        hdd.unmount()

def graceful_exit(all_hdds: list[HDD]):
    def func(icon, item: str):
        unmount_all(all_hdds)
        icon.stop()
    return func

def main():
    # hide window
    kernel32 = ctypes.WinDLL("kernel32")
    user32 = ctypes.WinDLL("user32")
    hwnd = kernel32.GetConsoleWindow()
    if hwnd:
        user32.ShowWindow(hwnd, 0)

    with open("automount.json", encoding = "utf-8") as f:
        config = json.load(f)
    all_hdds = [HDD(**o, cache_dir = config["cache_dir"]) for o in config["drives"]]

    image = Image.open("automount.png")
    app = pystray.Icon(
        "automount",
        image,
        "Mount network directories via rclone",
        menu = pystray.Menu(
            *(pystray.MenuItem(d.current_label, d.callback) for d in all_hdds),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("\u2795 Mount all", lambda icon, item: mount_all(all_hdds)),
            pystray.MenuItem("\u2796 Unmount all", lambda icon, item: unmount_all(all_hdds)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", graceful_exit(all_hdds))
        )
    )

    try:
        os.mkdir("logs")
    except OSError:
        pass
    today = datetime.now()
    with open(f"logs/app.{today.strftime('%Y-%m-%d')}.log", "a", encoding = "utf-8", buffering = 1) as f:
        with contextlib.redirect_stdout(f):
            try:
                app.run()
            finally:
                unmount_all(all_hdds)
                app.stop()

if __name__ == "__main__":
    main()
