import os
import stat

import requests

# https://stackoverflow.com/questions/1094841/get-a-human-readable-version-of-a-file-size
def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

# class DownloadUtil:
def download_file(url: str, local_filename: str, logger = None):
    # STEP - make sure target path exists
    local_path = os.path.dirname(local_filename)
    if not os.path.exists(local_path):
        os.makedirs(local_path)
    if os.path.exists(local_filename):
        return False
    # STEP - Download the file
    tmp = local_filename + ".tmp"
    with requests.get(url, stream=True) as resp:
        resp.raise_for_status()
        file_size = int(resp.headers.get("Content-length" ))
        if logger:
            logger.info (f"Total file size: {sizeof_fmt(file_size)}.")
        chunk_size = 100*1024*1024 # 10MB chunks
        downloaded_so_far = 0

        with open(tmp, 'wb') as file:
            for chunk in resp.iter_content(chunk_size):
                if chunk:
                    file.write(chunk)
                    downloaded_so_far += len(chunk)
                    if logger:
                        logger.info(f"Downloaded so far: {sizeof_fmt(downloaded_so_far)}.")

    os.rename(tmp, local_filename)
    return True

def chmod_plus_exec(filename):
    permissions = os.stat(filename)
    os.chmod(filename, permissions.st_mode | stat.S_IEXEC)

def write_template(src: str, dest: str, chmod: bool = False, replace=None):
    if replace is None:
        replace = {}
    with open(src, 'r') as file:
        content = file.read()
    for k,v in replace.items():
        content = content.replace(k, v)
    with open(dest, "w", newline="\n") as f: # make sure we use Linux-style line endings, even on windows
        f.writelines(content)
    if chmod:
        chmod_plus_exec(dest)

def download_json(url: str):
    response = requests.get(url)
    if not 200 <= response.status_code < 300:
        raise Exception(f"Failed to download JSON from {url}. Status code: {response.status_code}, Response: {response.text}")
    return response.json()

def download_text(url: str):
    response = requests.get(url)
    return response