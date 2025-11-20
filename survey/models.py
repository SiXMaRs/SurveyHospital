from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings

class ServiceGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    def __str__(self):
        return self.name

class ServicePoint(models.Model):
    name = models.CharField(max_length=255, help_text="ชื่อจุดบริการ")
    code = models.CharField(max_length=50, unique=True, help_text="รหัส Code")

    group = models.ForeignKey(
        ServiceGroup, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="service_points",
        help_text="จุดบริการนี้ อยู่ในกลุ่มภารกิจใด"
    )

    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="managed_points",
        blank=True,
        help_text="Manager (User) ที่รับผิดชอบจุดบริการนี้"
    )

    def __str__(self):
        return f"{self.code} - {self.name}"
    
class Survey(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'ฉบับร่าง'   # ค่า Default ของเรา
        ACTIVE = 'ACTIVE', 'ใช้งานจริง'

    title_th = models.CharField(max_length=255, verbose_name="ชื่อแบบสอบถาม (TH)")
    title_en = models.CharField(max_length=255, verbose_name="ชื่อแบบสอบถาม (EN)", blank=True, null=True)
    description = models.TextField(blank=True, null=True, verbose_name="คำอธิบาย")
    
    version_number = models.CharField(max_length=50, verbose_name="เลขเวอร์ชัน", default="1.0")
    
    # [สำคัญ] ตั้ง default เป็น DRAFT
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.DRAFT, 
        verbose_name="สถานะ"
    )
    
    service_point = models.ForeignKey(
        'ServicePoint', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True, 
        related_name='surveys',
        verbose_name="จุดบริการที่ใช้งาน"
    )
    
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="สร้างโดย"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                original = Survey.objects.get(pk=self.pk)
                if original.title_th != self.title_th or original.title_en != self.title_en:
                    try:
                        parts = self.version_number.split('.')
                        self.version_number = f"{int(parts[0]) + 1}.0"
                    except (ValueError, IndexError):
                        self.version_number = "1.0"
            except Survey.DoesNotExist:
                pass 
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "1. แบบสอบถาม (Survey)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title_th} (v.{self.version_number})"

class Question(models.Model):
    """
    (โมเดลใหม่)
    คำถามจะ "ชี้" ไปที่ Survey (แม่) โดยตรง
    และมีแค่ 2 ประเภท
    """
    class QuestionType(models.TextChoices):
        RATING_5 = 'RATING_5', 'คะแนน 1-5 ดาว'
        TEXTAREA = 'TEXTAREA', 'ข้อความ (หลายบรรทัด)'

    # (แก้ไข) ชี้ไปที่ 'Survey' (แทน 'SurveyVersion')
    survey = models.ForeignKey(
        Survey, 
        on_delete=models.CASCADE, 
        related_name="questions",
        verbose_name="แบบสอบถาม"
    )
    
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, default=QuestionType.RATING_5, verbose_name="ประเภทคำถาม")
    text_th = models.TextField(verbose_name="ข้อความคำถาม (TH)")
    text_en = models.TextField(verbose_name="ข้อความคำถาม (EN)", blank=True, null=True)
    
    # (เรา "เก็บ" order ไว้ เพื่อเรียงลำดับคำถามใน Kiosk)
    order = models.PositiveIntegerField(default=0, verbose_name="ลำดับ")
    is_required = models.BooleanField(default=True, verbose_name="บังคับตอบ")
    
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="สร้างโดย",
        related_name="created_questions"
    )

    class Meta:
        verbose_name = "2. คำถาม (Question)"
        verbose_name_plural = "2. คำถาม (Question)"
        ordering = ['order']

    def __str__(self):
        return f"{self.order}. {self.text_th}"
    

# --- 3. ตารางกลุ่มเก็บคำตอบ (Response Data) ---
class Response(models.Model):
    """เก็บข้อมูลหัวบิล (Header) ของการตอบ 1 ครั้ง"""
    class PatientType(models.TextChoices):
        NEW = 'NEW', 'ผู้ป่วยใหม่'
        EXISTING = 'EXISTING', 'ผู้ป่วยเก่า (นัดหมาย)'
    class UserRole(models.TextChoices):
        PATIENT = 'PATIENT', 'ผู้ป่วย'
        RELATIVE = 'RELATIVE', 'ญาติ'
    class BenefitPlan(models.TextChoices):
        UC = 'UC', 'สิทธิบัตรทอง'
        SOCIAL_SECURITY = 'SOCIAL_SECURITY', 'ประกันสังคม'
        GOVERNMENT = 'GOVERNMENT', 'สิทธิข้าราชการ/เบิกจ่ายตรง'
        SELF_PAY = 'SELF_PAY', 'ชำระเงินเอง (เงินสด)'
        OTHER = 'OTHER', 'อื่น ๆ'
    class AgeRange(models.TextChoices):
        UNDER_15 = 'UNDER_15', 'ต่ำกว่า 15 ปี'
        R_15_25 = '15_25', '15-25 ปี'
        R_26_40 = '26_40', '26-40 ปี'
        R_41_60 = '41_60', '41-60 ปี'
        OVER_60 = 'OVER_60', 'มากกว่า 60 ปี'
    class Gender(models.TextChoices):
        MALE = 'MALE', 'ชาย'
        FEMALE = 'FEMALE', 'หญิง'
        OTHER = 'OTHER', 'อื่น ๆ'
        NOT_SPECIFIED = 'NOT_SPECIFIED', 'ไม่ระบุ'

    # [แก้ไข] เปลี่ยนชื่อจาก survey_version เป็น survey เพื่อให้ตรงกับ views.py
    survey = models.ForeignKey(
        Survey, 
        on_delete=models.PROTECT,
        verbose_name="แบบสอบถาม"
    )
    
    service_point = models.ForeignKey(
        ServicePoint, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="จุดบริการ"
    )
    
    # Technical fields
    client_ip = models.GenericIPAddressField(blank=True, null=True, verbose_name="Client IP")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    hn_hash = models.CharField(max_length=255, blank=True, null=True, verbose_name="HN (Hashed)")
    pdpa_accepted = models.BooleanField(default=False, verbose_name="ยอมรับ PDPA")

    # Demographics
    patient_type = models.CharField(max_length=20, choices=PatientType.choices, blank=True, null=True, verbose_name="ประเภทผู้ป่วย")
    user_role = models.CharField(max_length=20, choices=UserRole.choices, blank=True, null=True, verbose_name="ผู้ตอบ")
    benefit_plan = models.CharField(max_length=30, choices=BenefitPlan.choices, blank=True, null=True, verbose_name="สิทธิการรักษา")
    benefit_plan_other = models.CharField(max_length=255, blank=True, null=True, verbose_name="สิทธิอื่น ๆ")
    age_range = models.CharField(max_length=20, choices=AgeRange.choices, blank=True, null=True, verbose_name="ช่วงอายุ")
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True, null=True, verbose_name="เพศ")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="เวลาเริ่มตอบ")
    submitted_at = models.DateTimeField(blank=True, null=True, verbose_name="เวลากดส่ง")

    class Meta:
        verbose_name = "การตอบกลับ (Response)"
        verbose_name_plural = "การตอบกลับ (Responses)"

    def __str__(self):
        return f"Response #{self.id} on {self.survey}"

class ResponseAnswer(models.Model):
    """ (3. ผ่าตัดตารางนี้ - ตามแนวคิดที่ "ถูกต้อง") """
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True) 

    # (ลบ 'option' และ 'answer_value' เก่าทิ้ง)
    
    # (เพิ่ม 2 ฟิลด์ใหม่สำหรับ "ตัวเลข" และ "ข้อความ" แยกกัน)
    answer_rating = models.PositiveIntegerField(null=True, blank=True, verbose_name="คำตอบ (คะแนน)")
    answer_text = models.TextField(null=True, blank=True, verbose_name="คำตอบ (ข้อความ)")

    class Meta:
        verbose_name = "คำตอบย่อย"
        verbose_name_plural = "คำตอบย่อย"

    def __str__(self):
        if self.answer_rating is not None:
            return f"Ans Q#{self.question_id}: {self.answer_rating} ดาว"
        return f"Ans Q#{self.question_id}: {self.answer_text}"


# --- 4. ตารางกลุ่มแจ้งเตือน & ตรวจสอบ (Admin Features) ---
class AlertRule(models.Model):
    class ConditionType(models.TextChoices):
        EQUALS = 'EQUALS', 'เท่ากับ'
        NOT_EQUALS = 'NOT_EQUALS', 'ไม่เท่ากับ'
        LESS_THAN = 'LESS_THAN', 'น้อยกว่า'
        GREATER_THAN = 'GREATER_THAN', 'มากกว่า'
        CONTAINS = 'CONTAINS', 'มีคำว่า'

    name = models.CharField(max_length=255, verbose_name="ชื่อกฎแจ้งเตือน")
    survey_version = models.ForeignKey(Survey, on_delete=models.CASCADE, verbose_name="เวอร์ชันแบบสอบถาม")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, verbose_name="คำถามที่ตรวจสอบ")
    condition_type = models.CharField(max_length=20, choices=ConditionType.choices, verbose_name="เงื่อนไข")
    condition_value = models.CharField(max_length=255, verbose_name="ค่าที่ตรวจสอบ (เช่น 6 หรือ ID ตัวเลือก)")
    is_active = models.BooleanField(default=True, verbose_name="ใช้งาน")
    created_by_user = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="สร้างโดย"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่สร้าง")

    class Meta:
        verbose_name = "กฎการแจ้งเตือน"
        verbose_name_plural = "กฎการแจ้งเตือน"

class Alert(models.Model):
    class Status(models.TextChoices):
        NEW = 'NEW', 'ใหม่'
        ACKNOWLEDGED = 'ACKNOWLEDGED', 'รับทราบแล้ว'
        RESOLVED = 'RESOLVED', 'แก้ไขแล้ว'

    response = models.ForeignKey(Response, on_delete=models.CASCADE, verbose_name="การตอบกลับ")
    rule = models.ForeignKey(AlertRule, on_delete=models.PROTECT, verbose_name="กฎที่ตรง")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, verbose_name="สถานะ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="เวลาเกิด")
    resolved_at = models.DateTimeField(blank=True, null=True, verbose_name="เวลาแก้ไข")
    resolved_by_user = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name="ผู้แก้ไข"
    )

    class Meta:
        verbose_name = "การแจ้งเตือน (Alert)"
        verbose_name_plural = "การแจ้งเตือน (Alerts)"

class AuditLog(models.Model):
    user = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="ผู้กระทำ"
    )
    action = models.CharField(max_length=100, verbose_name="การกระทำ")
    table_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="ตาราง")
    record_id = models.BigIntegerField(blank=True, null=True, verbose_name="Record ID")
    details = models.JSONField(blank=True, null=True, verbose_name="รายละเอียด (ก่อน/หลัง)")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP Address")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="เวลา")

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-created_at']