from django.db import models
from django.contrib.auth.models import User

class ServicePoint(models.Model):
    """
    ตารางสำหรับเก็บ 49 จุดให้บริการ
    Admin จะเป็นคนสร้าง 49 รายการนี้ใน /admin/
    """
    name = models.CharField(max_length=255, help_text="เช่น 'จุดเจาะเลือด Lab 1'")
    code = models.CharField(max_length=50, unique=True, help_text="รหัส Kiosk เช่น 'LAB-01'")
    
    # --- นี่คือหัวใจของระบบ ---
    # เราผูก "จุดบริการ" เข้ากับ "ผู้ใช้" (Manager)
    # related_name='managed_points' ทำให้เราสามารถเรียก
    # user.managed_points.all() เพื่อดูว่า Manager คนนี้ดูแลจุดไหนบ้าง
    managers = models.ManyToManyField(
        User, 
        related_name="managed_points",
        blank=True, # Manager 1 คนอาจดูแล 0 หรือ หลายจุดก็ได้
        help_text="Manager ที่รับผิดชอบจุดบริการนี้"
    )

    def __str__(self):
        return f"{self.code} - {self.name}"