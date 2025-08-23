from src.subprocess_util import SubProcess
from src.models import LoggerInterface


class ScpUtil:
    def __init__(self, logger: LoggerInterface, instance_dns, pem_path, webserver_dns):
        self.logger = logger
        self.instance_dns = instance_dns
        self.pem_path = pem_path
        self.webserver_dns = webserver_dns

    def push_file(self, file_name):
        file_name = str(file_name)
        target_filename = file_name.split("/")[-1]
        cmd = f"scp -i  {self.pem_path}  {file_name} ec2-user@{self.webserver_dns}:~"
        stdout, stderr, return_code = SubProcess.run_cmd_light(cmd)
        if return_code != 0:
            raise Exception(f"Error for {file_name}. Error: {stderr}")

        cmd = f"ssh -i {self.pem_path} ec2-user@{self.webserver_dns} 'echo \"\" | sudo -S mv /home/ec2-user/{target_filename} /var/www/html/'"
        stdout, stderr, return_code = SubProcess.run_cmd_light(cmd)
        if return_code != 0:
            raise Exception(f"Error for {file_name}. Error: {stderr}")
        print(f"pushed file {file_name}")
