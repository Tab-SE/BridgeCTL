import slack_sdk
from slack_sdk.errors import SlackApiError
from src.models import LoggerInterface


class SlackNotifier:
    def __init__(self, logger: LoggerInterface, api_token):
        self.logger = logger
        self.api_token = api_token

    def _create_client(self):
        if not self.api_token:
            self.logger.error("Slack 'api_token' not set")
            return None
        return slack_sdk.WebClient(token=self.api_token)

    @staticmethod
    def lookup_slack_user_by_email(client, email):
        """
        Look up slack user by email address.
        """
        user_id = None
        err_msg = None
        try:
            response = client.users_lookupByEmail(email=email)
            user_id = response.data['user']['id']
        except SlackApiError as error:
            err_msg = error.response['error']
        return user_id, err_msg

    def send_private_message(self, email, text):
        try:
            client = self._create_client()
            if not client:
                return
            if not email:
                self.logger.info(f"not sending slack message because email is empty: '{email}'")
                return
            user_id, err_msg = self.lookup_slack_user_by_email(client, email)
            if not user_id:
                if err_msg in ["", "users_not_found"]:
                    svc_msg = f"WARNING: unable to send slack message because the email '{email}' is not a valid slack id"
                else:
                    svc_msg = f"Unexpected error message '{err_msg}' while sending slack message to email {email}"
                self.logger.warning(svc_msg)
                return
            self.logger.info(f"sending slack message to {email}")
            response = client.conversations_open(users=[user_id])
            user_email_channel = response.data['channel']['id']
            client.chat_postMessage(channel=user_email_channel, text=text)
        except Exception as ex:
            self.logger.error(f"error while sending private slack message:{ex}")

    def send_channel_message(self, channel, text):
        try:
            client = self._create_client()
            if not client:
                return
            client.chat_postMessage(channel=channel, text=text)
            self.logger.info(f"sent slack message to channelID {channel}")
        except Exception as ex:
            self.logger.error(f"error while sending message to slack channel id {channel}:{ex}")
