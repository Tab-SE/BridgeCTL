from pathlib import Path
from src.subprocess_util import SubProcess


class S3Client:
    is_valid_credentials = None

    def _check_credentials(self):
        if self.is_valid_credentials is None:
            _, stderr, return_code = SubProcess.run_cmd_light("aws sts get-caller-identity --no-cli-pager")
            if return_code != 0:
                raise Exception(f"AWS credentials invalid. {stderr}")
            self.is_valid_credentials = True

    def download_file(self, object_url: str, local_folder: Path):
        self._check_credentials()
        local_f = str(local_folder)
        if not local_f.endswith("/"):
            local_f += "/"
        cmd = f"aws s3 cp {object_url} {local_f}"
        stdout, stderr, return_code = SubProcess.run_cmd_light(cmd)
        if return_code != 0:
            raise Exception(f"Error downloading driver from S3 at {object_url}. Error: {stderr}")
