import requests

from src.models import LoggerInterface


class PagerDutyClient:
    def __init__(self, service_key, logger: LoggerInterface):
        self.service_key = service_key #= os.getenv('pager_duty_routing_key')
        self.logger = logger

    def has_service_key(self):
        return bool(self.service_key)

    def trigger_pagerduty_alert(self, incident_title, incident_details):
        url = "https://events.pagerduty.com/v2/enqueue"
        headers = {
            'Content-Type': 'application/json',
        }
        payload = {
            "routing_key": self.service_key,
            "event_action": "trigger",
            "payload": {
                "summary": incident_title,
                "source": "bridgectl",  # Customize this as per your source tool
                "severity": "error",  # Can be 'info', 'warning', 'error', or 'critical'
                "custom_details": incident_details
            }
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 202:
            self.logger.info("Alert triggered successfully in PagerDuty.")
        else:
            self.logger.error(f"Failed to trigger alert: {response.text}")
