import json
from http.client import responses
from typing import List

import requests

from src.lib.tc_api_client import tc_api_version, TCApiClient




class TCApiClientJobs(TCApiClient):
    def get_jobs_public(self) -> dict:
        headers = {**self._headers, **{
            'X-Tableau-Auth': self.session_token
        }}
        r = requests.get(f"{self.tc_pod_url}/api/{tc_api_version}/sites/{self.site_luid}/jobs", headers=headers)
        status_text = f"{responses[r.status_code]}"
        if r.status_code != 200:
            raise Exception(f"unable to get jobs. {status_text}, {r.content}")

        response = json.loads(r.content)
        return response

    def get_jobs_sorted(self, site_id):
        """
        get jobs from Tableau Cloud Private api
        """
        body = {
            "method": "getBackgroundJobs",
            "params": {"filter":
                {"operator": "and",
                 "clauses": [
                    {"operator": "in", "field": "taskType", "values":
                        [   "Extract",
                            "Bridge"]},
                    {"operator": "eq", "field": "siteId", "value": site_id}
                ]},
               "order": [{"field": "jobRequestedTime", "ascending": False}],
               "page": {"startIndex": 0, "maxItems": 1000}}
        }
        # ["Extract",
        #  "Flow",
        #  "PredictiveModelFlow",
        #  "Subscription",
        #  "Encryption",
        #  "Bridge",
        #  "Acceleration"]

        return self._post_private("/vizportal/api/web/v1/getBackgroundJobs", body)

    # @json_file_cache("jobs_cache.json")
    def get_job_detail(self, job_id):
        """
        get job detail from Tableau Cloud Private api
        """
        body = {
            "method": "getBackgroundJobExtendedInfo",
            "params": {
                "backgroundJobId": job_id}
        }
        return self._post_private("/vizportal/api/web/v1/getBackgroundJobExtendedInfo", body)

    def start_tasks(self, task_ids: List[str]):
        body = {
            "method": "runExtractTasks",
            "params": {
                "ids": task_ids}
        }
        return self._post_private("/vizportal/api/web/v1/runExtractTasks", body)

    def get_tasks(self, site_id):
        body = {
            "method": "getExtractTasks",
            "params": {
                    "filter": {
                      "operator": "and",
                      "clauses": [
                        {
                          "operator": "eq",
                          "field": "siteId",
                          "value": site_id
                        }
                      ]
                    },
            },
            "order": [
                      {
                        "field": "targetName",
                        "ascending": True
                      }
                    ],
            "page": {
              "startIndex": 0,
              "maxItems": 10
            }
        }
        tasks_result = self._post_private("/vizportal/api/web/v1/getExtractTasks", body)
        tasks = tasks_result.get("result", {}).get("tasks", [])
        datasources = tasks_result.get("result", {}).get("datasources", [])
        for task in tasks:
            target_id = task["targetId"]
            matching_datasources = [ds for ds in datasources if ds["id"] == target_id]
            if matching_datasources:
                task["datasource_name"] = matching_datasources[0]["name"]
            else:
                task["datasource_name"] = "Unknown"
        return tasks_result
