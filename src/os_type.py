import sys


class OsType:
    mac = 'mac'
    win = 'win'
    linux = 'linux'


def current_os():
    if sys.platform in ['win32', 'win64']:
        return OsType.win
    elif sys.platform == 'darwin':
        return OsType.mac
    elif sys.platform == 'linux':
        return OsType.linux
    else:
        return f'unknown os {sys.platform}'



