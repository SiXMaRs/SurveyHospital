from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

class ServiceGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    def __str__(self):
        return self.name

class ServicePoint(models.Model):
    name = models.CharField(max_length=255, help_text="ชื่อจุดบริการ")
    name_en = models.CharField(max_length=200, blank=True, null=True)
    code = models.CharField(max_length=50, unique=True, help_text="รหัส Code")

    @property
    def name_display(self):
        """เช็คภาษาปัจจุบัน แล้วเลือก field ที่ถูกต้อง"""
        if get_language() == 'en' and self.name_en:
            return self.name_en
        return self.name

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
    description_en = models.TextField(blank=True, null=True)
    version_number = models.CharField(max_length=50, verbose_name="เลขเวอร์ชัน", default="1.0")
    
    @property
    def title_display(self):
        if get_language() == 'en' and self.title_en:
            return self.title_en
        return self.title_th

    @property
    def description_display(self):
        if get_language() == 'en' and self.description_en:
            return self.description_en
        return self.description
    
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
        TEXTAREA = 'TEXTAREA', 'ข้อความ'

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
    
    @property
    def text_display(self):
        if get_language() == 'en' and self.text_en:
            return self.text_en
        return self.text_th
    
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
        UNDER_20 = 'UNDER_20', _('ต่ำกว่า 20 ปี')
        R_20_39 = '20_39', _('20-39 ปี')
        R_40_59 = '40_59', _('40-59 ปี')
        OVER_60 = 'OVER_60', _('60 ปีขึ้นไป')
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



from django.contrib.auth.models import User

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications') # แจ้งเตือนใคร
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True, null=True) # ลิงก์ไปหน้าดูผล
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notify {self.recipient.username}: {self.title}"
    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    line_user_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="LINE User ID")