import requests
import json
from django.conf import settings
from django.core.mail import send_mail
import logging
logger = logging.getLogger(__name__)

def send_line_push(message, recipient_id):
    """
    ฟังก์ชันส่งข้อความไปยัง LINE User ID หรือ Group ID ที่กำหนด
    recipient_id: LINE User ID (Uxxxx...) หรือ Group ID (Cxxxx...)
    """
    url = 'https://api.line.me/v2/bot/message/push'
    access_token = settings.LINE_CHANNEL_ACCESS_TOKEN 
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    
    payload = {
        "to": recipient_id,
        "messages": [
            {"type": "text", "text": message}
        ]
    }
    
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5)
        r.raise_for_status() # Raise exception ถ้า status code ไม่ใช่ 2xx
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"LINE API Error to {recipient_id}: {r.status_code} - {r.text if 'r' in locals() else e}")
        return False
    
def send_email_alert(subject, message, recipient_list):
    """ฟังก์ชันสำหรับส่งอีเมลแจ้งเตือน"""
    try:
        # ใช้ค่า SMTP จาก settings.py
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL, 
            recipient_list,
            fail_silently=False, 
        )
        print(f"✅ Email alert sent successfully to {recipient_list}")
        return True
    except Exception as e:
        print(f"🚨 Failed to send email alert: {e}")
        return False