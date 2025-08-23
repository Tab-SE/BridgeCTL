#!/usr/bin/env python3

"""
### BridgeCTL Description ###
This module downloads and installs Tableau BridgeCTL. It will do the following:
- download the latest bridgectl zip pkg from the github releases
- install pip modules
- create a shortcut command 'bridgectl' on mac, windows, or linux shell
- start bridgectl
Note that this script only uses libraries from the Python standard library so that it will work on a clean install of Python.
"""
import os
import os.path
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from fnmatch import fnmatch
from urllib.error import HTTPError
from urllib.request import urlopen
from pathlib import Path

TARGET_GITHUB_REPO = "<target_github_repo>"
LATEST_VERSION = "<latest_version>"
def is_internalbuild():
    return TARGET_GITHUB_REPO.endswith("tableautest.com")

print("")
print("")
print("============================================")
print("=== Welcome to Tableau BridgeCTL Setup  ====")
print("============================================")

print(f"Installing BridgeCTL version: {LATEST_VERSION}")
print("\nSTEP - System pre-checks")
print("check operating system")


class OsType:
    mac = 'mac'
    linux = 'linux'
    win = 'win'


if sys.platform == 'darwin':
    current_os = OsType.mac
elif sys.platform == 'linux':
    current_os = OsType.linux
elif sys.platform in ['win32', 'win64']:
    current_os = OsType.win
else:
    print(f"  error: operating system {sys.platform} is not supported")
    exit(1)
print(f"  ✓ - running on {current_os}")

# STEP - System Checks
if (Path(os.getcwd()) / ".git").exists() or (Path(os.getcwd()) / ".." / ".git").exists():
    print("error: install not supported where .git directory found")
    exit(1)
if current_os == OsType.win:
    windows_not_allowed_paths = ["c:\\", "c:\\windows\\system32"]
    if os.getcwd().lower() in windows_not_allowed_paths:
        print(r"error: install under C:\ or C:\Windows\System32 is not supported. Please use a different directory.")
        exit(1)
if os.getcwd().lower().endswith('downloads'):
    print(r"WARNING: install under ~/Downloads or USER\Downloads is not recommended.")

py_version_required = '3.10.7'
print(f"check python version")
py_version = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
print(f"  ✓ - python version {py_version} installed")
required_major, required_minor, required_micro = map(int, py_version_required.split('.'))
current_major, current_minor, current_micro = sys.version_info.major, sys.version_info.minor, sys.version_info.micro

if (current_major, current_minor, current_micro) < (required_major, required_minor, required_micro):
    print(f"  error: python version {py_version_required} or higher is required. "
          f"Please upgrade at https://www.python.org/downloads")
    sys.exit(1)

update_mode = len(sys.argv) > 1 and sys.argv[1] == 'update'
if update_mode:
    """ double check we aren't running from source code directory, since update-mode deletes files """
    print(f"setup mode: {update_mode}")
    current_file = os.path.abspath(__file__)
else:
    print("setup mode: new install")
print(f"current directory: {os.getcwd()}")

if not update_mode:
    if not sys.stdin.isatty():
        print("This script requires interactive input to confirm install.")
    else:
        answer = input("\nWould you like to install BridgeCTL in the current directory? (yes/no): ")
        if answer.lower() not in ['yes', 'y']:
            print("setup cancelled")
            exit()

def urlopen_with_retry(url):
    mtries, mdelay, backoff = 4, 0.5, 2
    while mtries > 1:
        try:
            return urlopen(url)
        except HTTPError:
            print(f"HTTP error: Retrying in {mdelay} seconds...")
            time.sleep(mdelay)
            mtries -= 1
            mdelay *= backoff

    print(f"Error: Unable to get url {url}")
    exit(1)


def delete_folders(folders):
    print("\nSTEP - delete current folders")
    for folder in folders:
        folder_full_path = os.getcwd() + os.path.sep + folder
        if os.path.exists(folder_full_path):
            print(f"   deleting '{folder}'")
            shutil.rmtree(folder_full_path)

# STEP - Prepare to download zip
TARGET_DIR = 'bridgectl'
OLD_DIR = "old_bridgectl"
if update_mode:
    delete_folders(["src"])
else:
    if not os.path.exists(TARGET_DIR):
        print("create 'bridgectl' directory")
        os.mkdir(TARGET_DIR)
    else:
        print("'bridgectl' directory already exists, python files will be overwritten with the new version. "
              "Configuration and log files will be preserved.")
    os.chdir(TARGET_DIR)

zip_filename = f"bridgectl_v{LATEST_VERSION}.zip"
local_zip_dest = os.getcwd() + os.path.sep + zip_filename

print('\nSTEP - Download latest setup pkg')
manually_downloaded_zip = Path.cwd().parent / zip_filename
if manually_downloaded_zip.exists():
    print("already downloaded")
    shutil.move(manually_downloaded_zip, local_zip_dest)
else:
    if is_internalbuild():
        download_setup_pkg_url = f"http://{TARGET_GITHUB_REPO}/{zip_filename}"
        print(f"downloading pkg from {download_setup_pkg_url}")
        response_pkg = urlopen_with_retry(download_setup_pkg_url)
        with open(local_zip_dest, 'wb') as f:
            f.write(response_pkg.read())
    else:
        download_setup_pkg_url = f"https://github.com/{TARGET_GITHUB_REPO}/releases/download/{LATEST_VERSION}/{zip_filename}"
        print(f"downloading pkg from {download_setup_pkg_url}")
        response_pkg = urlopen_with_retry(download_setup_pkg_url)
        with open(local_zip_dest, 'wb') as f:
            f.write(response_pkg.read())

print(f"extracting to {os.getcwd()}")
with zipfile.ZipFile(local_zip_dest, 'r') as zip_ref:
    zip_ref.extractall(os.getcwd())

if update_mode:
    print(f"cleanup old zip files")
    for zip_file in [x for x in os.listdir(os.getcwd()) if fnmatch(x, "bridgectl*.zip")]:
        print(f"  deleting {zip_file}")
        os.unlink(zip_file)

def print_errors_from_log(logfile: str):
    if not os.path.exists(logfile):
        print(f"error: log file {logfile} not found")
        return
    with open(logfile) as lf:
        for line in lf.readlines():
            if 'error:' in line.lower():
                print(line)


print("\nSTEP - Create python virtual environment")
VENV_DIR = 'tabenv'
bin_folder = 'Scripts' if current_os == OsType.win else 'bin'
venv_python = os.path.abspath(os.path.join(VENV_DIR, bin_folder, 'python'))
venv_dir_abs = os.path.abspath(VENV_DIR)

print(f"Create python venv at: {venv_dir_abs}")
if not os.path.exists(venv_dir_abs):
    cmd = [sys.executable, "-m", "venv", VENV_DIR]
    subprocess.run(cmd, check=True)
    print(f"  created successfully")
    cmd = [venv_python, "-m", "ensurepip"]
    subprocess.run(cmd, check=True)
    print(f"  ensured pip in venv")
else:
    print(f"  already exists")

print("\nSTEP - Install pip modules")
requirements_file = os.getcwd() + os.path.sep + 'requirements.txt'
PIP_INSTALL_LOG_FILE = "pip-install.log"

if os.path.exists(PIP_INSTALL_LOG_FILE):
    os.remove(PIP_INSTALL_LOG_FILE)
try:
    print(f"Please wait, this can take a couple minutes to complete ...")
    cmd = [venv_python, "-m", "pip", "install", "-qq", "--log", PIP_INSTALL_LOG_FILE, "--no-warn-script-location", "-r", requirements_file]
    print(f"executing command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
except Exception as e:
    print(f"Error installing dependencies:\n{e}\n")
    print(f"Check below errors from log file: {PIP_INSTALL_LOG_FILE}\n")
    print(" --------------------------------")
    print_errors_from_log(PIP_INSTALL_LOG_FILE)
    sys.exit(1)


print("\nSTEP - create shortcut function 'bridgectl'")
bridgectl_dir = os.getcwd()


def update_profile_file_mac_linux(profile_file, shortcut_command, newline):
    marker = "Added by BridgeCTL"  # Use marker to select lines
    lmarker = "# " + marker
    print(f"Adding 'bridgectl' shortcut function marked by '{marker}' to '{profile_file}'")
    updated = False
    lines = []
    if os.path.exists(profile_file):
        with open(profile_file) as cf:
            lines = cf.readlines()
        for i, l in enumerate(lines):
            if lmarker in l:
                print("  Marker block found - updating shortcut function")
                lines[i + 1] = shortcut_command
                updated = True
                break
    else:
        print(f"  {profile_file} file not found and will be created")
    if not updated:
        print("  Marker block not found, adding shortcut function")
        lines.append(lmarker + newline)
        lines.append(shortcut_command)
        lines.append(lmarker + newline)
    with open(profile_file, "w") as cf:
        cf.writelines(lines)


def add_alias_function_to_bash_or_zsh():
    # Check if user shell is ZSH
    user_shell = os.getenv("SHELL", "")
    if "/zsh" in user_shell:
        profile_file = f"{os.environ['HOME']}/.zshrc"
    elif "/bash" in user_shell:
        profile_file = f"{os.environ['HOME']}/.bashrc"
    else:
        print(f"warning: user shell is set to '{user_shell}'. Only 'zsh' and 'bash' are supported")
        return
    shortcut_command = 'bridgectl() { (cd "' + bridgectl_dir + '" && ' + venv_python + ' start.py $@) }\n'
    update_profile_file_mac_linux(profile_file, shortcut_command, newline="\n")


# -- begin: Code to support updating PATH on windows
if current_os == OsType.win:
    import winreg
    import ctypes

    def append_path_envvar_windows(add_path):
        print(f"Adding directory '{add_path}' to Windows user PATH to enable 'bridgectl' shortcut command")
        def canonical(path):
            # Expand environment variables and normalize the path
            path = os.path.expandvars(path)
            path = os.path.normpath(path).upper().rstrip(os.sep)
            return path
        canpath = canonical(add_path)

        # Get current user PATH from the registry
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_READ) as key:
                cur_path, _ = winreg.QueryValueEx(key, 'PATH')
        except FileNotFoundError:
            cur_path = ''

        new_path = []
        shortcut_new = True
        changed = False

        for p in cur_path.split(os.pathsep):
            if 'BRIDGECTL' in canonical(p):
                # Replace existing 'bridgectl' shortcut if the path is different
                if canpath != canonical(p):
                    new_path.append(add_path)
                    changed = True
                shortcut_new = False
            else:
                new_path.append(p)

        if shortcut_new:
            new_path.append(add_path)
            changed = True

        if changed:
            new_path_str = os.pathsep.join(new_path)
            # Set the user PATH in the registry
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, new_path_str)
            print("  Added/updated PATH.")
            # Notify the system about the environment variable change
            broadcast_environment_change()
        else:
            print("  Already in PATH.")

    def broadcast_environment_change():
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_long()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            'Environment',
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result)
        )
# -- end: Code to support updating PATH on windows


def create_bridgectl_cmd_windows():
    print(f"creating bridgectl.cmd shortcut script in current directory")
    shortcut_dir = os.getcwd() + os.sep + "shortcut"
    if not os.path.exists(shortcut_dir):
        os.mkdir(shortcut_dir)
    cmd_file = shortcut_dir + os.sep + "bridgectl.cmd"
    lines = ['@echo off',
             'setlocal',
             f'cd /d "{os.getcwd()}"',
             f'"{venv_python}" start.py %*',
             'endlocal']
    with open(cmd_file, "w") as cf:
        cf.write("\n".join(lines))
    append_path_envvar_windows(shortcut_dir)
    return cmd_file

try:
    if current_os in [OsType.mac, OsType.linux]:
        add_alias_function_to_bash_or_zsh()
    elif current_os == OsType.win:
        win_bridgectl_cmd = create_bridgectl_cmd_windows()
except Exception as ex:
    print("unable to add 'bridgectl' shortcut. error:")
    traceback.print_exc()

print()
print("================================================")
print("=== BridgeCTL setup completed successfully  ====")
print("================================================")

print("\nSTEP - Start")
print("TIP: To start bridgectl without the shortcut command, run the command:")
print(f'```\ncd "{os.getcwd()}" && {venv_python} start.py\n```')
if update_mode:
    print("\nupdate complete\n\n\n")
    if current_os in [OsType.mac, OsType.linux, OsType.win]:
        print("Please type 'bridgectl' to start updated version\n\n")
else:
    os.unlink(__file__)

    is_terminal = os.isatty(sys.stdout.fileno())
    if not is_terminal:
        print("Type 'bridgectl' to start\n\n")
        exit(0)
    print(f"starting BridgeCTL")
    if current_os in [OsType.mac, OsType.linux]:
        start_command = [venv_python, 'start.py']
        s = ' '.join(start_command)
        subprocess.run(start_command)
    elif current_os == OsType.win:
        subprocess.run([win_bridgectl_cmd])
