import pystray
from PIL import Image
import subprocess
import threading
import json
import signal
import os
import contextlib
from datetime import datetime, timezone
import ctypes

#=============================================================================================================================#

class HDD:
    def __init__(self, *, hostname: str, mount_dir: str, mount_point: str, volume_name: str = "HDD", cache_dir: str = "temp", extra_args: list[str] = []):
        self.hostname = hostname
        self.mount_dir = mount_dir
        self.mount_point = mount_point
        self.volume_name = volume_name
        try:
            os.mkdir(cache_dir)
        except OSError:
            pass
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

    def is_mounted(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def mount(self):
        with self._lock:
            if not self.is_mounted():
                self.process = subprocess.Popen(
                    [
                        "C:\\bin\\rclone",
                        "mount", f"{self.hostname}:{self.mount_dir}", self.mount_point,
                        "--volname", self.volume_name,
                        "--vfs-cache-mode", "writes",
                        "--cache-dir", f"{self.cache_dir}\\{self.mount_dir}",
                        "--file-perms", "0777",
                        "--dir-perms", "0777",
                        "--no-modtime",
                        "--no-console"
                    ],
                    stdin = subprocess.PIPE,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.STDOUT,
                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                )
                threading.Thread(target = self.log_to_stdout).start()

    def unmount(self):
        with self._lock:
            if self.is_mounted():
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
                self.process.wait()
                self.process = None

    def remount(self):
        self.unmount()
        self.mount()

    def current_label(self, icon):
        if self.is_mounted():
            return f"\u2705 {self.volume_name}"
        else:
            return f"\U0001f6ab {self.volume_name}"

    def construct_submenu(self):
        return [
            pystray.MenuItem("Mount", lambda icon, item: self.mount(), enabled = lambda icon: not self.is_mounted()),
            pystray.MenuItem("Unmount", lambda icon, item: self.unmount(), enabled = lambda icon: self.is_mounted()),
            pystray.MenuItem("Remount", lambda icon, item: self.remount(), enabled = lambda icon: self.is_mounted()),
        ]

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
    try:
        os.mkdir("logs")
    except OSError:
        pass
    today = datetime.now(tz = timezone.utc)
    with open(f"logs/app.{today.strftime('%Y-%m-%d')}.log", "a", encoding = "utf-8", buffering = 1) as f:
        with contextlib.redirect_stdout(f):
            with open("automount.json", encoding = "utf-8") as f:
                config = json.load(f)
            all_hdds = [HDD(**o) for o in config["drives"]]

            image = Image.open("automount.png")
            app = pystray.Icon(
                "automount",
                image,
                "Mount network directories via rclone",
                menu = pystray.Menu(
                    *(pystray.MenuItem(d.current_label, pystray.Menu(d.construct_submenu)) for d in all_hdds),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("\u2795 Mount all", lambda icon, item: mount_all(all_hdds)),
                    pystray.MenuItem("\u2796 Unmount all", lambda icon, item: unmount_all(all_hdds)),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Exit", graceful_exit(all_hdds))
                )
            )

            try:
                # create headless console
                kernel32 = ctypes.WinDLL("kernel32", use_last_error = True)
                console = subprocess.Popen(
                    "echo ready & cmd pause",
                    stdin = subprocess.PIPE,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.DEVNULL,
                    shell = True
                )
                console.stdout.readline()
                kernel32.AttachConsole(console.pid)

                app.run()
            except:
                import traceback
                print(traceback.format_exc())
            finally:
                unmount_all(all_hdds)
                app.stop()
                console.kill()

if __name__ == "__main__":
    main()
