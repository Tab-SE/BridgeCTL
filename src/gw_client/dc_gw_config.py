import os
from dataclasses import dataclass


url = os.getenv("DC_GW_BASE_URL")
if url:
    DC_GW_BASE_URL = url
else:
    DC_GW_BASE_URL = "https://gw-api-93411b1c1737.herokuapp.com"

REMOTE_COMMAND_INTERVAL_SECONDS = 30

@dataclass
class DcGwConfig:
    gw_api_base_url: str = None
    gw_token: str = None
