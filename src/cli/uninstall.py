import os
import shutil
import sys

from src.cli.app_config import APP_NAME_FOLDER

SHELL_PROFILE_MARKER = "Added by BridgeCTL"  # Use marker to select lines


def get_unix_shell_profile(user_shell):
    if "/zsh" in user_shell:
        return f"{os.environ['HOME']}/.zshrc"
    elif "/bash" in user_shell:
        return f"{os.environ['HOME']}/.bashrc"
    else:
        return None


# def manual_uninstall_helper():
#     msg = f"""
#     # On Linux or MacOS
#     rm -rf {os.getcwd()}
#
#     # On Windows
#     rmdir /s {os.getcwd()}
#     """
#     print()
#     print(f"You can manually uninstall {APP_NAME} by running following commands:")
#     print(msg)
#     print("Then remove it from your shell profile / PATH")
#     if current_os() == OsType.linux or current_os() == OsType.mac:
#         user_shell = os.getenv("SHELL", "")
#         profile_path = get_unix_shell_profile(user_shell)
#         if profile_path:
#             print(f"Remove lines between markers {SHELL_PROFILE_MARKER} in the {profile_path}")
#         else:
#             print(f"Remove lines between markers {SHELL_PROFILE_MARKER} in your shell ({user_shell}) profile")
#     elif current_os() == OsType.win:
#         pass


def remove_alias_on_unix():
    user_shell = os.getenv("SHELL", "")
    profile_file = get_unix_shell_profile(user_shell)
    if not profile_file:
        print(f"warning: user shell is set to '{user_shell}'. Only 'zsh' and 'bash' are supported")
        print(f"please remove manually alias `bridgectl` from you shell profile")
        return

    if not os.path.exists(profile_file):
        return
    # Check we have correct markers in file
    res = []
    marker_count = 0
    with open(profile_file, "r") as f:
        for line in f.readlines():
            if SHELL_PROFILE_MARKER in line:
                marker_count += 1
            elif marker_count == 0 or marker_count == 2:
                res.append(line)

    if marker_count == 2:
        with open(profile_file, "w") as f:
            f.writelines(res)
        print(f"Alias `bridgectl` successfully removed from {profile_file}")
    else:
        print(f"There was an error trying to remove alias `bridgectl` from your shell profile {profile_file}")
        print(f"please remove manually.")


def remove_bridgectl_folder():
    print(f"Removing {APP_NAME_FOLDER} folder and its contents: {os.getcwd()}")
    shutil.rmtree(os.getcwd())
    print("Done")
    sys.exit(1)
