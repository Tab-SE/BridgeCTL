import json
import requests

from src.models import LoggerInterface


class NewRelicClient:
    def __init__(self, logger: LoggerInterface, insert_key: str, account_id: str):
        self.insert_key = insert_key
        self.account_id = account_id
        self.logger = logger

    def has_credentials(self):
        return bool(self.insert_key and self.account_id)

    def trigger_newrelic_alert(self, incident_title: str, incident_details: str):
        url = f"https://insights-collector.newrelic.com/v1/accounts/{self.account_id}/events"
        headers = {
            "Content-Type": "application/json",
            "X-Insert-Key": self.insert_key
        }
        payload = {
            "eventType": "BridgeCtlAlert",
            "title": incident_title,
            "message": incident_details,
            "source": "bridgectl",
            "severity": "error"
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            self.logger.info("Alert triggered successfully in NewRelic.")
            return True
        else:
            self.logger.error(f"Failed to trigger NewRelic alert: {response.text}")
            return False 