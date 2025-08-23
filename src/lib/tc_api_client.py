import json
from dataclasses import dataclass
from http.client import responses
from typing import List

import requests

from src.models import PatToken

tc_api_version = "3.24"
# information about api versions: https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_versions.htm


@dataclass
class LoginResult:
    is_success: bool = None
    status_code: int = None
    status_text: str = None
    site_luid: str = None
    session_token: str = None #perhaps rename to "tableau_auth_token"
    user_id: str = None
    tc_pod_url: str = None
    error: str = ""


class TableauCloudLogin:
    @staticmethod
    def login(pat: PatToken, raise_if_not_success: bool = False) -> LoginResult:
        if not pat.name:
            raise ValueError("pat.name is empty")
        if not pat.secret:
            raise ValueError("pat.secret is empty")
        if not pat.sitename:
            raise ValueError("pat.sitename is empty")
        if not pat.get_pod_url():
            raise ValueError("pat.pod_url is empty")

        body = {
            "credentials": {
                "personalAccessTokenName": pat.name,  # note this field is not really used, so can be anything.
                "personalAccessTokenSecret": pat.secret,
                "site": {
                    "contentUrl": pat.sitename
                }
            }
        }
        headers = {
            'accept': 'application/json',
        }
        r = requests.post(f"{pat.get_pod_url()}/api/{tc_api_version}/auth/signin", json=body, headers=headers, timeout=10)
        status_text = f"{responses[r.status_code]}"
        result = LoginResult()
        result.is_success = r.status_code == 200
        result.status_code = r.status_code
        result.status_text = status_text
        result.tc_pod_url = pat.get_pod_url()
        if result.is_success:
            response = json.loads(r.content)
            result.session_token = response["credentials"]["token"] # this token is called a "authentication token" or a "JOT"
            result.site_luid = response["credentials"]["site"]["id"]
            result.user_id = response["credentials"]["user"]["id"]
        else:
            result.error = result.status_text
            if raise_if_not_success:
                raise Exception(f"unable to login with pat token {pat.name}. status_text: {result.status_text}")
        return result

    @staticmethod
    def logout(pod_url: str, session_token: str):
        if not pod_url or not session_token:
            return
        headers = {
            'accept': 'application/json',
            'X-tableau-auth': session_token
        }
        res_signout = requests.post(f"{pod_url}/api/{tc_api_version}/auth/signout", headers=headers)
        if not res_signout.ok:
            print(f"Warning. unable to signout. status_code: {res_signout.status_code}, status_text: {res_signout.text}")

    @staticmethod
    def is_token_valid(pat: PatToken) -> LoginResult:
        r=TableauCloudLogin.login(pat)
        if r.is_success:
            TableauCloudLogin.logout(pat.get_pod_url(), r.session_token)
        return r


class TCApiClient:
    _headers = {'Accept': 'application/json',
                'Content-Type': 'application/json'}
    xsrf_value = "9f3WV3ekuJmVEA" # this can be any string, it is used by the server to prevent cross-site scripting attacks.

    def __init__(self, login_result: LoginResult):
        self.session_token = login_result.session_token
        self.tc_pod_url = login_result.tc_pod_url
        self.site_luid = login_result.site_luid

    def _post_private(self, url_part: str, body: dict):
        header_values = {**self._headers, **{
            "X-Xsrf-Token": self.xsrf_value,
            "Cookie": f"workgroup_session_id={self.session_token}; XSRF-TOKEN={self.xsrf_value}"
        }}
        r = requests.post(f"{self.tc_pod_url}{url_part}", headers=header_values, json=body)
        r.raise_for_status()
        return json.loads(r.content)
    
    def _get_public(self, url_part: str):
        header_values = {**self._headers, **{
            "X-tableau-auth": self.session_token
        }}
        r = requests.get(f"{self.tc_pod_url}{url_part}", headers=header_values)
        r.raise_for_status()
        return json.loads(r.content)

    def _post_public(self, url_part: str, payload: dict):
        header_values = {**self._headers, **{
            "X-tableau-auth": self.session_token
        }}
        r = requests.post(f"{self.tc_pod_url}{url_part}", headers=header_values, json=payload)
        if r.status_code != 200:
            error_message = f"Status code: {r.status_code}. Response: {r.text}"
            raise RuntimeError(error_message)
        return r.json()

    def logout(self):
        TableauCloudLogin.logout(self.tc_pod_url, self.session_token)

    def get_bridge_settings(self, site_id: str):
        body = {
            "method": "getSiteBridgeSettingsForSiteAdmin",
            "params": {
                "id": site_id
            }
        }
        return self._post_private("/vizportal/api/web/v1/getSiteBridgeSettingsForSiteAdmin", body)

    def get_agent_connection_status(self):
        body = {
            "method": "getSiteRemoteAgentsConnectionStatus",
            "params": {}}
        return self._post_private("/vizportal/api/web/v1/getSiteRemoteAgentsConnectionStatus", body)

    def get_edge_pools(self, site_id: str):
        body = {
            "method": "getEdgePools",
            "params": {
                "siteId": site_id
            }
        }
        return self._post_private("/vizportal/api/web/v1/getEdgePools", body)

    def delete_bridge_agent(self, owner_id: str, device_id: str):
        body = {"method": "deleteUserRemoteAgents",
                "params": {
                    "ownerId": owner_id,
                    "deviceIds": [device_id]
                }}
        return self._post_private("/vizportal/api/web/v1/deleteUserRemoteAgents", body)

    def get_session_info(self):
        body = {
            "method": "getSessionInfo",
            "params": {}
        }
        return self._post_private(f'/vizportal/api/web/v1/getSessionInfo', body)

    def get_personal_access_token_info(self, user_id: str):
        body = {
            "method": "getPersonalAccessTokenNames",
            "params": {
                "userId": user_id
            }
        }
        return self._post_private("/vizportal/api/web/v1/getPersonalAccessTokenNames", body)

@dataclass
class BridgePool:
    id: str = None
    name: str = None

@dataclass
class BridgeAgentPool:
    agent_id: str = None
    agent_name: str = None
    pool_id: str = None
    pool_name: str = None

class TCApiLogic:
    def __init__(self, login_result: LoginResult):
        self.api = TCApiClient(login_result)

    def get_pools_for_site(self, site_id):
        pass

    def get_bridge_status(self, site_id):
        # Get connection status
        status_ret = self.api.get_agent_connection_status()
        status = {}
        if "result" in status_ret and "agents" in status_ret["result"]:
            for b in status_ret["result"]["agents"]:
                status[b["agentName"]] = b["connectionStatus"]

        # Get pools information
        pools_ret = self.api.get_edge_pools(site_id)
        agents = []
        
        # Safely extract pool information
        if "result" in pools_ret:
            result = pools_ret["result"]
            success_data = result.get("success", {})
            user_pools = success_data.get("userDefinedPools", {})
            for pool in user_pools.values():
                for agent in pool.get("agents", {}).values():
                    agent["poolName"] = pool.get("displayName", "Unknown Pool")
                    agents.append(agent)
            default_agents = success_data.get("defaultPoolAgents", {})
            for agent in default_agents.values():
                agent["poolName"] = "(default)"
                agents.append(agent)
            unassigned_agents = success_data.get("unassignedAgents", {})
            for agent in unassigned_agents.values():
                agent["poolName"] = "(unassigned)"
                agents.append(agent)

        # Create rows with safe dictionary access
        rows = []
        for b in agents:
            rows.append([
                b.get("agentName", "Unknown"),
                b.get("poolName", "Unknown"),
                b.get("ownerFriendlyName", "Unknown"),
                b.get("version", ""),
                status.get(b.get("agentName", ""), "Unknown"),
                b.get("lastUsed", "")
            ])
        
        return rows

    def get_pool_list(self, site_id) -> List[BridgePool]:
        pool_response = self.api.get_edge_pools(site_id)
        pool_list = []
        if "success" not in pool_response["result"] or "userDefinedPools" not in pool_response["result"]["success"]:
            return pool_list
        for k, v in pool_response["result"]["success"]["userDefinedPools"].items():
            bp = BridgePool(v["id"], v["displayName"])
            pool_list.append(bp)
        return pool_list

    def get_bridge_pool_mapping(self, site_id) -> List[BridgeAgentPool]:
        pool_response = self.api.get_edge_pools(site_id)
        mappings = []
        
        if "success" not in pool_response["result"]:
            return mappings
            
        success = pool_response["result"]["success"]
        
        # Process user-defined pools
        if "userDefinedPools" in success:
            for pool_id, pool_data in success["userDefinedPools"].items():
                pool_name = pool_data["displayName"]
                
                # Process agents in this pool
                if "agents" in pool_data:
                    for agent_id, agent_data in pool_data["agents"].items():
                        mapping = BridgeAgentPool(
                            agent_id=agent_id,
                            agent_name=agent_data["agentName"],
                            pool_id=pool_id,
                            pool_name=pool_name
                        )
                        mappings.append(mapping)
        
        # Process default pool agents
        if "defaultPoolAgents" in success:
            for agent_id, agent_data in success["defaultPoolAgents"].items():
                mapping = BridgeAgentPool(
                    agent_id=agent_id,
                    agent_name=agent_data["agentName"],
                    pool_id="default",
                    pool_name="(default)"
                )
                mappings.append(mapping)
                
        # Process unassigned agents
        if "unassignedAgents" in success:
            for agent_id, agent_data in success["unassignedAgents"].items():
                mapping = BridgeAgentPool(
                    agent_id=agent_id,
                    agent_name=agent_data["agentName"],
                    pool_id="unassigned",
                    pool_name="(unassigned)"
                )
                mappings.append(mapping)
                
        return mappings

    def does_token_have_site_admin_privileges(self) -> (bool, str):
        ret = self.api.get_session_info()
        role = ret['result']['site']['role']
        if "Administrator" in role:
            return True, None
        return False, f"role {role} does not contain 'Administrator'"
