from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings

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
    # use AUTH_USER_MODEL to support custom user models
    # If AUTH_USER_MODEL is not defined in settings, fall back to the default 'auth.User'
    managers = models.ManyToManyField(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        related_name="managed_points",
        blank=True, # Manager 1 คนอาจดูแล 0 หรือ หลายจุดก็ได้
        help_text="Manager ที่รับผิดชอบจุดบริการนี้"
    )

    def __str__(self):
        return f"{self.code} - {self.name}"
    
class Survey(models.Model):
    """
    ตารางแม่ของแบบสอบถาม (ตัวหลัก)
    เช่น "แบบสอบถามความพึงพอใจ รพ.ตระการพืชผล"
    """
    title = models.CharField(max_length=255, verbose_name="ชื่อแบบสอบถาม")
    description = models.TextField(blank=True, null=True, verbose_name="คำอธิบาย")
    created_by_user = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'), # เชื่อมโยงไปที่ User (Admin/Manager) with fallback
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="สร้างโดย"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่สร้าง")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="แก้ไขล่าสุด")

    class Meta:
        verbose_name = "แบบสอบถาม (Survey)"
        verbose_name_plural = "แบบสอบถาม (Surveys)"

    def __str__(self):
        return self.title

class SurveyVersion(models.Model):
    """
    ตารางเวอร์ชันของแบบสอบถาม (v1, v2)
    นี่คือ "ตัวจริง" ที่จะถูกนำไปผูกกับ ServicePoint
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'ฉบับร่าง'
        ACTIVE = 'ACTIVE', 'ใช้งาน'
        ARCHIVED = 'ARCHIVED', 'เก็บถาวร'

    survey = models.ForeignKey(
        Survey, 
        on_delete=models.CASCADE, 
        related_name="versions",
        verbose_name="แบบสอบถามหลัก"
    )
    version_number = models.PositiveIntegerField(default=1, verbose_name="เวอร์ชันที่")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="สถานะ"
    )
    default_lang = models.CharField(max_length=10, default='th', verbose_name="ภาษาหลัก")
    published_at = models.DateTimeField(blank=True, null=True, verbose_name="วันที่เริ่มใช้งาน")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่สร้าง")
    
    # ตารางเชื่อม ManyToMany ว่าเวอร์ชันนี้ ให้แสดงที่จุดบริการใดบ้าง
    service_points = models.ManyToManyField(
        ServicePoint,
        through='SurveyServicePoint', # ใช้ตารางเชื่อมด้านล่าง
        related_name='survey_versions',
        verbose_name="จุดบริการที่ใช้งาน"
    )

    class Meta:
        verbose_name = "เวอร์ชันแบบสอบถาม"
        verbose_name_plural = "เวอร์ชันแบบสอบถาม"
        unique_together = ('survey', 'version_number')

    def __str__(self):
        return f"{self.survey.title} (v{self.version_number})"

class SurveyServicePoint(models.Model):
    """
    ตารางเชื่อม (Junction Table) ระหว่าง SurveyVersion และ ServicePoint
    เพื่อกำหนดว่าเวอร์ชันไหน แสดงที่จุดไหน (ฟีเจอร์ 2)
    """
    survey_version = models.ForeignKey(SurveyVersion, on_delete=models.CASCADE)
    service_point = models.ForeignKey(ServicePoint, on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = "การกำหนดจุดบริการ"
        verbose_name_plural = "การกำหนดจุดบริการ"
        unique_together = ('survey_version', 'service_point')

    def __str__(self):
        return f"{self.survey_version} @ {self.service_point}"

class Section(models.Model):
    """
    ตารางส่วน (หรือหน้า) ของแบบสอบถาม
    เช่น "ส่วนที่ 1: ข้อมูลทั่วไป"
    """
    survey_version = models.ForeignKey(
        SurveyVersion, 
        on_delete=models.CASCADE, 
        related_name="sections",
        verbose_name="เวอร์ชันแบบสอบถาม"
    )
    title_content = models.JSONField(verbose_name="ชื่อส่วน (JSON)")
    description_content = models.JSONField(blank=True, null=True, verbose_name="คำอธิบาย (JSON)")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ลำดับ")

    class Meta:
        verbose_name = "ส่วน (Section)"
        verbose_name_plural = "ส่วน (Sections)"
        ordering = ['sort_order']

    def __str__(self):
        return self.title_content.get('th', f'Section {self.id}')

class Question(models.Model):
        """
        ตารางคำถามแต่ละข้อ
        """
        # --- นี่คือส่วนที่แก้ไข ---
        class QuestionType(models.TextChoices):
            RATING_5 = 'RATING_5', 'คะแนน 1-5 ดาว (Rating)'
            TEXTAREA = 'TEXTAREA', 'ตอบยาว (Textarea)'
        # --- จบส่วนแก้ไข ---

        section = models.ForeignKey(
            Section, 
            on_delete=models.CASCADE, 
            related_name="questions",
            verbose_name="ส่วน"
        )
        question_type = models.CharField(
            max_length=20,
            choices=QuestionType.choices,
            verbose_name="ประเภทคำถาม"
        )
        text_content = models.JSONField(verbose_name="ข้อความคำถาม (JSON)")
        is_required = models.BooleanField(default=False, verbose_name="บังคับตอบ")
        sort_order = models.PositiveIntegerField(default=0, verbose_name="ลำดับ")
        
        # Skip Logic ยังคงใช้ได้ ถ้าคุณต้องการซ่อน Textarea
        skip_logic = models.JSONField(blank=True, null=True, verbose_name="Skip Logic (JSON)")

        class Meta:
            verbose_name = "คำถาม"
            verbose_name_plural = "คำถาม"
            ordering = ['sort_order']

        def __str__(self):
            return self.text_content.get('th', f'Question {self.id}')

class QuestionOption(models.Model):
    """
    ตารางตัวเลือกของคำถาม (สำหรับ Radio, Checkbox)
    """
    question = models.ForeignKey(
        Question, 
        on_delete=models.CASCADE, 
        related_name="options",
        verbose_name="คำถาม"
    )
    text_content = models.JSONField(verbose_name="ข้อความตัวเลือก (JSON)")
    value = models.CharField(max_length=100, blank=True, null=True, verbose_name="ค่าที่เก็บจริง")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ลำดับ")

    class Meta:
        verbose_name = "ตัวเลือกคำถาม"
        verbose_name_plural = "ตัวเลือกคำถาม"
        ordering = ['sort_order']

    def __str__(self):
        return self.text_content.get('th', f'Option {self.id}')


# --- 3. ตารางกลุ่มเก็บคำตอบ (Response Data) ---

class Response(models.Model):
    """
    ตารางข้อมูลส่วนหัวของการตอบ 1 ครั้ง (1 แถว = 1 การส่ง)
    รวมถึงข้อมูลประชากรที่ผู้ตอบกรอก
    """
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

    survey_version = models.ForeignKey(
        SurveyVersion, 
        on_delete=models.PROTECT, # ป้องกันการลบเวอร์ชันที่มีคนตอบแล้ว
        verbose_name="เวอร์ชันแบบสอบถาม"
    )
    service_point = models.ForeignKey(
        ServicePoint, # (เปลี่ยนชื่อจาก Channel)
        on_delete=models.SET_NULL, # ถ้าลบจุดบริการ ให้ยังเก็บ Response ไว้
        null=True,
        verbose_name="จุดบริการ"
    )
    
    client_ip = models.GenericIPAddressField(blank=True, null=True, verbose_name="Client IP")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    hn_hash = models.CharField(max_length=255, blank=True, null=True, verbose_name="HN (Hashed)")
    pdpa_accepted = models.BooleanField(default=False, verbose_name="ยอมรับ PDPA")

    # Anonymous Demographics
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
        return f"Response #{self.id} on {self.survey_version}"

class ResponseAnswer(models.Model):
    """
    ตารางคำตอบย่อยของแต่ละคำถาม (1 แถว ต่อ 1 คำตอบ)
    """
    response = models.ForeignKey(
        Response, 
        on_delete=models.CASCADE, 
        related_name="answers",
        verbose_name="การตอบกลับ"
    )
    question = models.ForeignKey(
        Question, 
        on_delete=models.SET_NULL, # ถ้าลบคำถาม ให้ยังเก็บคำตอบไว้
        null=True,
        verbose_name="คำถาม"
    )
    option = models.ForeignKey(
        QuestionOption, 
        on_delete=models.SET_NULL, # ถ้าลบตัวเลือก ให้ยังเก็บคำตอบไว้
        blank=True, 
        null=True,
        verbose_name="ตัวเลือกที่ตอบ"
    )
    answer_value = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="ค่าที่ตอบ (Text, NPS, Rating)"
    )

    class Meta:
        verbose_name = "คำตอบย่อย"
        verbose_name_plural = "คำตอบย่อย"

    def __str__(self):
        return f"Answer for Q#{self.question_id} on Response#{self.response_id}"


# --- 4. ตารางกลุ่มแจ้งเตือน & ตรวจสอบ (Admin Features) ---

class AlertRule(models.Model):
    """
    ตารางสำหรับ "ตั้งค่า" ว่าจะแจ้งเตือนเมื่อไหร่ (ฟีเจอร์ 5)
    เช่น ถ้า NPS < 6
    """
    class ConditionType(models.TextChoices):
        EQUALS = 'EQUALS', 'เท่ากับ'
        NOT_EQUALS = 'NOT_EQUALS', 'ไม่เท่ากับ'
        LESS_THAN = 'LESS_THAN', 'น้อยกว่า'
        GREATER_THAN = 'GREATER_THAN', 'มากกว่า'
        CONTAINS = 'CONTAINS', 'มีคำว่า'

    name = models.CharField(max_length=255, verbose_name="ชื่อกฎแจ้งเตือน")
    survey_version = models.ForeignKey(SurveyVersion, on_delete=models.CASCADE, verbose_name="เวอร์ชันแบบสอบถาม")
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
    """
    ตารางผลลัพธ์การแจ้งเตือนที่เกิดขึ้นจริง (ที่ Admin ต้องมาจัดการ)
    """
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
    """
    สมุดพกสำหรับตรวจสอบการกระทำของผู้ดูแลระบบ (Admin/Manager)
    """
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