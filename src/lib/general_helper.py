import base64
import hashlib
import os
import random
import re
import shutil
import string
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import yaml


class FileHelper:
    @staticmethod
    def replace_text(template_file: str or Path, out_file: str or Path, replace: dict):
        if template_file:
            shutil.copy(template_file, out_file)
        with open(out_file, 'r+') as f:
            content = f.read()
            for k, v in replace.items():
                if v is None:
                    raise ValueError(f"value of {k} is not set, unable to replace value")
                content = content.replace(k, str(v))
            f.seek(0)
            f.write(content)
            f.truncate()

    @staticmethod
    def replace_line_starts_with(file: Path, starts_with_replace: dict):
        with open(file, 'r') as f:
            lines = f.readlines()
        with open(file, 'w') as f:
            for line in lines:
                for k, v in starts_with_replace.items():
                    if line.startswith(k):
                        line = v + '\n'
                        break
                f.write(line)

    @staticmethod
    def encode_file_to_base64(file_path):
        with open(file_path, 'rb') as file:
            file_data = file.read()
            base64_encoded_data = base64.b64encode(file_data)
            return base64_encoded_data.decode('utf-8')

    @staticmethod
    def decode_base64_to_file(base64_string, output_file_path):
        decoded_data = base64.b64decode(base64_string)
        with open(output_file_path, 'wb') as file:
            file.write(decoded_data)


    @staticmethod
    def convert_line_endings(file_path):
        """Convert CRLF line endings to LF in a file."""
        # with open(file_path, 'r') as file:
        #     content = file.read()
        # with open(file_path, 'w', newline="\n") as file:
        #     file.write(content)
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        content = content.replace('\r\n', '\n')
        with open(file_path, 'w', newline='\n', encoding='utf-8') as file:
            file.write(content)

    @staticmethod
    def list_files(path: str, include_pattern: str = None) -> List[str]:
        """
        Lists files in the given directory path, optionally filtering them by a regex pattern,
        sorted by last modification date.

        :param path: The directory path to list files from.
        :param include_pattern: Optional regex pattern to filter files. Only files matching the pattern will be included.
        :return: A list of file names sorted by modification date.
        """
        pattern = re.compile(include_pattern) if include_pattern else None
        files_with_dates = []
        for item_name in os.listdir(path):
            full_path = os.path.join(path, item_name)
            if os.path.isfile(full_path):
                if not pattern or pattern.search(item_name):
                    # Get the last modification time and append to the list with file name
                    mod_time = os.path.getmtime(full_path)
                    files_with_dates.append((item_name, mod_time))

        # Sort the files by last modification date
        files_with_dates.sort(key=lambda x: x[1], reverse=True)
        return [file for file, mod_time in files_with_dates]

    @staticmethod
    def list_folders(path):
        if not os.path.exists(path):
            return []
        for item_name in os.listdir(path):
            if os.path.isdir(os.path.join(path, item_name)):
                yield item_name

    @staticmethod
    def sort_by_modified(files):
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        # return sorted(files, key=os.path.getmtime)

    @staticmethod
    def extract_single_tar_content_to_text(tar_path, output_text_path):
        with tarfile.open(tar_path, 'r') as tar:
            member = tar.getmembers()[0]
            if not member.isfile():
                raise Exception(f"tar file {tar_path} does not contain a file")
            file_object = tar.extractfile(member)
            if not file_object:
                raise Exception(f"tar file {tar_path} does not contain a file")
            file_content = file_object.read()
            # Open the output text file
            # Use 'wb' for binary file types, 'w' for text files
            with open(output_text_path, 'wb') as output_file:
                output_file.write(file_content)

    @staticmethod
    def validate_yaml(yaml_content):
        try:
            content = yaml.safe_load(yaml_content)
            if "clusters" not in content:
                return "Invalid YAML content.  Missing 'clusters' section"
            if "current-context" not in content:
                return "Invalid YAML content.  Missing 'current-context' property"
        except yaml.YAMLError as e:
            return f"Invalid YAML content.  {e}"


class StringUtils:
    @staticmethod
    def format_token_prefix(site_name: str, pool_name: str):
        site_name = re.sub(r'[^a-z0-9-]', '', site_name.lower())[:12]
        pool_name = re.sub(r'[^a-z0-9-]', '', pool_name.lower())[:25]
        return f"bridge-{site_name}-{pool_name}-"

    @staticmethod
    def current_datetime() -> str:
        return datetime.now().strftime('%Y%m%d%H%M%S')

    @staticmethod
    def current_datetime_seconds() -> str:
        return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    @staticmethod
    def current_timestamp() -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def format_date_to_minutes(date_obj: datetime) -> str:
        return date_obj.strftime("%Y-%m-%d %H:%M %Z")

    @staticmethod
    def get_values_from_class(obj):
        values = []
        for k, v in vars(obj).items():
            if not k.startswith("__"):
                values.append(v)
        return values

    @staticmethod
    def print_property_values(obj, hide: list = None, skip: list = None):
        for k, v in obj.__dict__.items():
            display = v
            if skip and k in skip:
                continue
            if hide and k in hide:
                display = "xxxxx" # obfuscate value
            print(f"{k}: {display}")

    @classmethod
    def get_random_string(cls, length: int):
        letters_and_digits = string.ascii_lowercase #+ string.digits
        result_str = ''.join(random.choice(letters_and_digits) for _ in range(length))
        return result_str
        # return ''.join(random.choice(string.ascii_letters) for i in range(param))

    def convert_utc_to_local(self, utc):
        # self.local_tz = pytz.timezone(local_tz)
        from dateutil import tz

        from_zone = tz.tzutc()
        to_zone = tz.tzlocal()

        # utc = datetime.utcnow()
        # utc = datetime.strptime('2011-01-21 02:37:21', '%Y-%m-%d %H:%M:%S')

        # Tell the datetime object that it's in UTC time zone since
        # datetime objects are 'naive' by default
        utc = utc.replace(tzinfo=from_zone)

        # Convert time zone
        local_time = utc.astimezone(to_zone)
        return local_time

        self.local_tz = get_localzone()

    def convert_utc_to_local2(self, utc):
        from datetime import datetime
        import pytz
        utc = datetime.strptime(utc, "%Y-%m-%dT%H:%M:%S.%fZ")
        utc = pytz.utc.localize(utc)

        local_time = utc.astimezone(self.local_tz)
        return local_time

    @staticmethod
    def B_to_gBits(bits):
        if not bits or not isinstance(bits, int):
            return bits
        gBits = bits / 1000 / 1000 / 1000
        return round(gBits, 1)

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def short_time_ago(event_date: datetime) -> str:
        """Returns a human-readable string representing how long ago an event occurred.
        
        Args:
            event_date: The datetime of the event
            
        Returns:
            String like "5 mins", "2 hours", "3 days" etc.
        """
        if not event_date:
            return ""
        
        delta = datetime.now(timezone.utc) - event_date
        
        # Handle future dates
        if delta.total_seconds() < 0:
            return "0 sec"
        
        # Days
        if delta.days > 0:
            s = "s" if delta.days > 1 else ""
            return f"{delta.days} day{s}"
        
        # Hours
        if delta.seconds >= 3600:
            hours = delta.seconds // 3600
            s = "s" if hours > 1 else ""
            return f"{hours} hour{s}"
        
        # Minutes
        if delta.seconds >= 60:
            minutes = delta.seconds // 60
            s = "s" if minutes > 1 else ""
            return f"{minutes} min{s}"
        
        # Seconds
        return f"{delta.seconds}s"

    @staticmethod
    def parse_time_string(event_date: str) -> datetime:
        sliced_string = event_date[:19]
        event_date_time = datetime.strptime(sliced_string, "%Y-%m-%dT%H:%M:%S")
        event_date_time = event_date_time.replace(tzinfo=timezone.utc)
        return event_date_time

    @staticmethod
    def is_valid_pat_url(url):
        if not url:
            return "URL is empty"
        if not url.startswith("https://"):
            return "URL must start with 'https://'"
        if not (url.endswith("online.tableau.com") or url.endswith("tabint.net") or url.endswith("sfdcfc.net")):
            return "URL must end with 'online.tableau.com' or 'tabint.net' or 'sfdcfc.net'"
        from urllib.parse import urlparse
        try:
            result = urlparse(url)
            if not result.netloc:
                return "URL is missing a network location (e.g., 'www.example.com')"
            return None
        except ValueError:
            return "URL is not properly formatted"

    @staticmethod
    def remove_before(text, delimiter):
        parts = text.split(delimiter)
        if len(parts) > 1:
            return delimiter + parts[1]
        else:
            return text

    @staticmethod
    def decode_base64_string(base64_string):
        decoded_data = base64.b64decode(base64_string).decode('utf-8')
        return decoded_data

    @staticmethod
    def encode_string_base64(input_string: str):
        encoded_bytes = base64.b64encode(input_string.encode())
        encoded_string = encoded_bytes.decode('utf-8')
        return encoded_string

    @staticmethod
    def val_or_empty(input_string: str):
        val = "" if input_string is None else input_string
        return val

    @staticmethod
    def hash_string(input_str: str):
        """ MD5 Hash of a string
        """
        hash_object = hashlib.md5()
        hash_object.update(input_str.encode())
        hash_digest = hash_object.hexdigest()
        return hash_digest

class MachineHelper:
    @staticmethod
    def get_hostname(full_network_name: bool = False):
        import socket
        hostname = socket.gethostname()
        if not full_network_name:
            hostname = hostname.split(".")[0]
        return hostname

class TimezoneOptions:
    timezone_options = {
        "0 UTC (Coordinated Universal Time)": 0,
        "-12 Y (Yankee Time Zone)": -12,
        "-11 SST (Samoa Standard Time)": -11,
        "-10 HST (Hawaii Standard Time)": -10,
        "-9 AKST (Alaska Standard Time)": -9,
        "-8 PST (Pacific Standard Time)": -8,
        "-7 MST (Mountain Standard Time)": -7,
        "-6 CST (Central Standard Time)": -6,
        "-5 EST (Eastern Standard Time)": -5,
        "-4 AST (Atlantic Standard Time)": -4,
        "-3 ADT (Argentina Time)": -3,
        "-2 GST (South Georgia Time)": -2,
        "-1 AZOT (Azores Time)": -1,
        "+1 CET (Central European Time)": 1,
        "+2 EET (Eastern European Time)": 2,
        "+3 AST (Arabia Standard Time)": 3,
        "+4 GST (Gulf Standard Time)": 4,
        "+5 IST (Indian Standard Time)": 5,
        "+6 BST (Bangladesh Standard Time)": 6,
        "+7 ICT (Indochina Time)": 7,
        "+8 AWST (Australian Western Standard Time)": 8,
        "+9 JST (Japan Standard Time)": 9,
        "+10 AEST (Australian Eastern Standard Time)": 10,
        "+11 SBT (Solomon Islands Time)": 11,
        "+12 NZST (New Zealand Standard Time)": 12,
    }

    @staticmethod
    def get_offset_int(timezone_str):
        if timezone_str not in TimezoneOptions.timezone_options:
            return 0
        return TimezoneOptions.timezone_options[timezone_str]

    @staticmethod
    def get_abbrev(timezone_str):
        if timezone_str not in TimezoneOptions.timezone_options:
            return "UTC"
        return timezone_str.split(" ")[1]
