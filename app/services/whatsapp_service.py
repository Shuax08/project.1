"""Meta Cloud API transport. Never log message bodies or bearer tokens."""
import requests
from flask import current_app


class WhatsAppDeliveryError(Exception):
    pass


def send_text(phone_number_id, recipient, body):
    token = current_app.config.get('WHATSAPP_ACCESS_TOKEN')
    if not token:
        raise WhatsAppDeliveryError('WHATSAPP_ACCESS_TOKEN is missing')
    version = current_app.config['WHATSAPP_GRAPH_VERSION']
    url = f'https://graph.facebook.com/{version}/{phone_number_id}/messages'
    try:
        response = requests.post(
            url,
            headers={'Authorization': f'Bearer {token}'},
            json={'messaging_product': 'whatsapp', 'recipient_type': 'individual',
                  'to': recipient, 'type': 'text', 'text': {'preview_url': False, 'body': body[:4096]}},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WhatsAppDeliveryError('Meta message delivery failed') from exc
