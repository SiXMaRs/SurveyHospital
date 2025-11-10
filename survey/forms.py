# GIST: file:/survey/forms.py (ฉบับแก้ไข Bug "ข้อมูลไม่มา")
from django.contrib import admin
from django import forms
from .models import Question, SurveyVersion, Survey, ServicePoint

# (ฟังก์ชัน helper สำหรับเพิ่ม Tailwind)
def add_tailwind_classes(form):
    tailwind_class = "w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
    for field_name, field in form.fields.items():
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs.update({'class': tailwind_class, 'rows': 3})
        elif isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            if isinstance(field.widget, forms.CheckboxInput):
                # (อันนี้สำหรับ 'is_required' ใน QuestionForm)
                field.widget.attrs.update({'class': 'h-5 w-5 text-blue-600 rounded border-gray-300 focus:ring-blue-500'})
            pass # (ถ้าเป็น CheckboxSelectMultiple (จุดบริการ) ให้ "ข้าม")
        else:
            field.widget.attrs.update({'class': tailwind_class})

# --- Form 1: Survey ---
class SurveyForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = ['title_th', 'title_en']
        labels = {'title_th': 'ชื่อแบบสอบถาม (TH)', 'title_en': 'ชื่อแบบสอบถาม (EN) (ไม่บังคับ)'}
    
    def __init__(self, *args, **kwargs):
        # (สำคัญ!) ต้องส่ง *args, **kwargs ไปด้วย
        super().__init__(*args, **kwargs) 
        add_tailwind_classes(self)
        
    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if user and not instance.created_by_user:
            instance.created_by_user = user
        if commit:
            instance.save()
        return instance

# --- Form 2: SurveyVersion ---
class SurveyVersionForm(forms.ModelForm):
    
    # (เราจะใช้ 'ModelMultipleChoiceField' เพื่อสร้าง Checkboxes)
    service_points = forms.ModelMultipleChoiceField(
        queryset=ServicePoint.objects.all().order_by('name'),
        required=False, # (อนุญาตให้ไม่เลือกเลย)
        label="จุดบริการ (กลุ่ม) ที่จะใช้แบบสอบถามนี้:",
        widget=admin.widgets.FilteredSelectMultiple(
            verbose_name="จุดบริการ",
            is_stacked=False # (False = แนวนอน, True = แนวตั้ง)
        )
    )

    class Meta:
        model = SurveyVersion
        # (เพิ่ม 'service_points' เข้าไปใน fields)
        fields = ['survey', 'version_number', 'status', 'service_points']
        labels = {
            'survey': 'แม่แบบ (Survey)',
            'version_number': 'ชื่อเวอร์ชัน (v1, ปี 2568)',
            'status': 'สถานะ',
        }
        # (เราไม่ต้องใส่ widget ที่นี่แล้ว เพราะเราประกาศ field เอง)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # (เรียก helper - มันจะข้าม service_points ให้เอง)
        add_tailwind_classes(self)

    def save(self, commit=True, user=None):
        # (โค้ด save() เหมือนเดิม)
        instance = super().save(commit=False)
        if user and not instance.created_by_user:
            instance.created_by_user = user
        if commit:
            instance.save()
            # (สำคัญ) Django ต้องการ .save_m2m() สำหรับ ManyToManyField
            self.save_m2m() 
        return instance


# --- Form 4: Question ---
class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        
        # --- (นี่คือส่วนที่แก้ไข) ---
        fields = ['survey_version', 'question_type', 'text_th', 'text_en', 'order', 'is_required']
        labels = {
            'survey_version': 'เวอร์ชันของแบบสอบถาม (Version)', 
            'question_type': 'ประเภทคำถาม',
            'text_th': 'ข้อความคำถาม (TH)',
            'text_en': 'ข้อความคำถาม (EN) (ไม่บังคับ)',
            'order': 'ลำดับ',
            'is_required': 'บังคับตอบ (Required)',
        }
    
    def __init__(self, *args, **kwargs):
        # (สำคัญ!) ต้องส่ง *args, **kwargs ไปด้วย
        super().__init__(*args, **kwargs)
        add_tailwind_classes(self)

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if user and not instance.created_by_user:
            instance.created_by_user = user
        if commit:
            instance.save()
        return instance