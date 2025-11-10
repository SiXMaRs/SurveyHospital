# GIST: file:/survey/admin.py (ฉบับสมบูรณ์)

from django.contrib import admin
from .models import (
    Survey, SurveyVersion,Question, QuestionOption,
    ServicePoint, SurveyServicePoint, Response, ResponseAnswer
)

# --- 1. ตารางเชื่อม (Inline) ---
# (ใช้สำหรับ SurveyVersionAdmin)
class SurveyServicePointInline(admin.TabularInline):
    model = SurveyServicePoint
    extra = 1 # (แสดงช่องว่างสำหรับเพิ่ม 1 ช่อง)
    # (ทำให้ช่อง ServicePoint ค้นหาได้)
    autocomplete_fields = ['service_point'] 

# --- 2. Admin หลัก ---

@admin.register(ServicePoint)
class ServicePointAdmin(admin.ModelAdmin):
     list_display = ('name', 'code')
     # (ต้องมี search_fields เพื่อให้ autocomplete ของ Inline ทำงาน)
     search_fields = ('name', 'code') 
     filter_horizontal = ('managers',)

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'service_point', 'survey_version', 'submitted_at')
    list_filter = ('service_point', 'survey_version')
    date_hierarchy = 'submitted_at'

@admin.register(ResponseAnswer)
class ResponseAnswerAdmin(admin.ModelAdmin):
    list_display = ('response', 'question_summary', 'answer_value_short')
    search_fields = ('answer_value',)
    
    @admin.display(description='Question')
    def question_summary(self, obj):
        return str(obj.question)[:50]

    @admin.display(description='Answer')
    def answer_value_short(self, obj):
        return str(obj.answer_value)[:50]

# --- 3. Admin ของระบบ Survey (ที่แก้ไขแล้ว) ---

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    # (Fix: 'title' -> 'title_th')
    list_display = ('title_th', 'created_by_user', 'created_at')
    search_fields = ('title_th',)

@admin.register(SurveyVersion)
class SurveyVersionAdmin(admin.ModelAdmin):
    # (Fix: ลบ 'published_at')
    list_display = ('__str__', 'survey', 'status', 'version_number')
    # (Fix: 'survey__title' -> 'survey__title_th')
    list_filter = ('status', 'survey__title_th')
    search_fields = ('version_number', 'survey__title_th')
    
    # (Fix Error E013: เปลี่ยน 'filter_horizontal' เป็น 'inlines')
    inlines = [SurveyServicePointInline]

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text_th', 'survey_version', 'question_type', 'order') # (แก้ 'section' เป็น 'survey_version')
    
    # (แก้ list_filter ให้สั้นลง)
    list_filter = ('question_type', 'survey_version__survey__title_th') 
    
    search_fields = ('text_th',)
    list_editable = ('order',)

@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    # (Fix: 'text_content' -> 'text_th', 'sort_order' -> 'order')
    list_display = ('text_th', 'question', 'order')
    search_fields = ('text_th',)
    list_editable = ('order',)