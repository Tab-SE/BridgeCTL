import ipaddress
import os
import subprocess
import sys
import random


def convert_bytes(num, is1024=True):
    """
    this function will convert bytes to MB.... GB... etc
    """
    s = ['bytes', 'Kb', 'Mb', 'Gb', 'Tb'] if is1024 else ['bytes', 'KB', 'MB', 'GB', 'TB']
    base = 1024.0 if is1024 else 1000.0
    for x in s:
        if num < base:
            return "%3.1f %s" % (num, x)
        num /= base


def file_size(file_path):
    """
    this function will return the file size
    """
    is1024 = True if sys.platform in ['win32', 'win64'] else False
    if os.path.isfile(file_path):
        file_info = os.stat(file_path)
        return convert_bytes(file_info.st_size, is1024=is1024)
    return 0


class InstanceIP(object):
    ping_timeout_sec: int
    ip: str

    def __init__(self, ip: str, ping_timeout_sec=1):
        self.ping_timeout_sec = ping_timeout_sec
        self.ip = ip

    def validate(self):
        try:
            ipaddress.ip_address(self.ip)
            return True
        except ValueError:
            return False

    def ping(self):
        if not self.validate():
            return False

        try:
            param = '-c'
            command = ['ping', param, '1', self.ip]
            return subprocess.call(command, timeout=self.ping_timeout_sec, stdout=subprocess.DEVNULL) == 0
        except:
            return False


def generate_rand_id():
    for f in range(1, 500):
        id_rand = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=5))
    return id_rand
