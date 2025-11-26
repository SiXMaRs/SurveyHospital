# services.py (หรือไฟล์ที่คุณเลือก)

from django.contrib.auth.models import User
from django.conf import settings
from .models import Notification # Model Notification ของคุณ
from .utils import send_line_push # ฟังก์ชันส่ง LINE ที่สร้างไว้
from .models import UserProfile, ServicePoint # Model Profile และ ServicePoint ของคุณ
import logging
logger = logging.getLogger(__name__)

def notify_on_low_score(service_point, score, detail_link):
    """จัดการแจ้งเตือนคะแนนต่ำทั้งหมด"""
    
    # 1. เตรียมข้อความและลิงก์
    title = f"🔴 คะแนนต่ำ: {service_point.name}"
    message = f"พบการประเมินคะแนน {score} ที่ {service_point.name}"
    # กำหนด URL ที่ Manager จะคลิกเข้าไปดู (อย่าลืมเปลี่ยน yourdomain.com)
    full_web_link = f"https://yourdomain.com{detail_link}" 
    line_message_template = f"🔔 [แจ้งเตือนด่วน]\n{title}\n{message}\n\nตรวจสอบ: {full_web_link}"

    # 2. ค้นหา Manager ที่เกี่ยวข้อง (Fan-out Logic)
    managers_qs = User.objects.filter(managed_points=service_point)

    for manager in managers_qs:
        # A. สร้าง Notification ใน Database (สำหรับแสดงในเว็บ)
        Notification.objects.create(
            recipient=manager,
            title=title,
            message=message,
            link=detail_link,
            is_read=False
        )
        
        # B. ส่ง LINE ไปหา Manager รายบุคคล (Uxxxx...)
        try:
            line_id = manager.profile.line_user_id
            if line_id:
                send_line_push(line_message_template, line_id)
        except UserProfile.DoesNotExist:
            logger.warning(f"UserProfile missing for Manager {manager.username}.")


    # 3. แจ้งเตือน LINE Admin กลาง
    admin_line_message = f"🚨 [Admin Alert]\nเกิดคะแนนต่ำที่: {service_point.name}\nคะแนน: {score}\n\nตรวจสอบ: {full_web_link}"
    send_line_push(admin_line_message, settings.LINE_ADMIN_RECIPIENT_ID)

    return True