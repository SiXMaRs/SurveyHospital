# ใน survey/admin.py
from django.contrib import admin
from .models import *


# ลงทะเบียนโมเดลอื่น ๆ เพื่อให้แสดงในหน้า Admin
class QuestionOptionInline(admin.TabularInline):
    """
    Inline สำหรับเพิ่ม 'ตัวเลือก' ในหน้า 'คำถาม'
    """
    model = QuestionOption
    verbose_name = "ตัวเลือก"
    verbose_name_plural = "ตัวเลือกคำถาม (Options)"
    extra = 3 # แสดงช่องว่าง 3 ช่องให้กรอก

class SectionInline(admin.StackedInline):
    """
    Inline สำหรับเพิ่ม 'ส่วน' ในหน้า 'เวอร์ชัน'
    (StackedInline เหมาะกับ Section เพราะมีหลาย field)
    """
    model = Section
    verbose_name = "ส่วน"
    verbose_name_plural = "ส่วน (หน้า) ของแบบสอบถาม"
    extra = 1 # แสดงช่องว่าง 1 ช่องให้กรอก

class SurveyServicePointInline(admin.TabularInline):
    """
    Inline สำหรับเชื่อม 'จุดบริการ' ในหน้า 'เวอร์ชัน'
    (นี่คือส่วนที่แก้ปัญหาให้คุณ)
    """
    model = SurveyServicePoint
    verbose_name = "จุดบริการ"
    verbose_name_plural = "จุดบริการที่ใช้งาน (Channels)"
    extra = 1
    # ถ้า ServicePoint มีเยอะมาก ให้ใช้ autocomplete
    autocomplete_fields = ['service_point']

class ResponseAnswerInline(admin.TabularInline):
    """
    Inline สำหรับ 'แสดง' คำตอบย่อย ในหน้า 'การตอบกลับ' (Response)
    (ตั้งค่าเป็น Read-Only)
    """
    model = ResponseAnswer
    readonly_fields = ('question', 'option', 'answer_value')
    can_delete = False
    extra = 0 # ไม่ต้องแสดงช่องให้เพิ่ม


# --- 2. CUSTOM ADMIN PAGES (การปรับแต่งหน้า Admin) ---

@admin.register(ServicePoint)
class ServicePointAdmin(admin.ModelAdmin):
    """
    ปรับแต่งหน้า ServicePoint (เพื่อให้ autocomplete ทำงาน)
    """
    list_display = ('id', 'name', 'code')  # แก้จาก location_details เป็น code ตามโมเดล
    search_fields = ('id', 'name', 'code')  # เพิ่ม code ใน search_fields ด้วย

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by_user', 'created_at')
    search_fields = ('title',)

@admin.register(SurveyVersion)
class SurveyVersionAdmin(admin.ModelAdmin):
    """
    นี่คือหน้า "หลัก" ในการสร้างแบบสอบถาม
    เราจะฝัง Section และ ServicePoint ไว้ในหน้านี้
    """
    list_display = ('__str__', 'survey', 'status', 'published_at')
    list_filter = ('status', 'survey__title')
    search_fields = ('survey__title', 'version_number')
    
    # นี่คือส่วนสำคัญ:
    inlines = [SectionInline, SurveyServicePointInline]

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    หน้าจัดการคำถาม
    เราจะฝัง "ตัวเลือก" (Options) ไว้ในหน้านี้
    """
    list_display = ('__str__', 'section', 'question_type', 'is_required')
    list_filter = ('question_type', 'section__survey_version__survey__title')
    search_fields = ('text_content',)
    
    # นี่คือส่วนสำคัญ:
    inlines = [QuestionOptionInline]

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    """
    หน้าแสดงผลการตอบกลับ (ตั้งค่าเป็น Read-Only)
    """
    list_display = ('id', 'survey_version', 'service_point', 'submitted_at')
    list_filter = ('survey_version', 'service_point', 'submitted_at')
    search_fields = ('id', 'hn_hash')
    
    # ทำให้ฟิลด์ทั้งหมดอ่านอย่างเดียว
    readonly_fields = [f.name for f in Response._meta.fields]
    
    # แสดงคำตอบย่อยที่เกี่ยวข้อง
    inlines = [ResponseAnswerInline]

    def has_add_permission(self, request):
        return False # ห้ามเพิ่ม Response ผ่านหน้า Admin

@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'survey_version', 'question', 'condition_type', 'condition_value', 'is_active')
    list_filter = ('is_active', 'survey_version')

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'response', 'rule', 'status', 'created_at')
    list_filter = ('status', 'rule__name')
    # แก้ไขได้แค่ status
    readonly_fields = ('response', 'rule', 'created_at') 

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'table_name', 'record_id')
    list_filter = ('action', 'user', 'table_name')
    
    # อ่านอย่างเดียวทั้งหมด
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

# --- 3. ลงทะเบียนโมเดลที่ไม่ต้องปรับแต่ง ---
# (เราไม่จำเป็นต้อง register โมเดลที่ถูก Inlines จัดการไปแล้ว)
#
# admin.site.register(Section) # -> ถูกจัดการโดย SurveyVersionAdmin
# admin.site.register(QuestionOption) # -> ถูกจัดการโดย QuestionAdmin
# admin.site.register(SurveyServicePoint) # -> ถูกจัดการโดย SurveyVersionAdmin
# admin.site.register(ResponseAnswer) # -> ถูกจัดการโดย ResponseAdmin
    