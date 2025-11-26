from django import forms
from survey.models import *

class ManagerSurveyForm(forms.ModelForm):
    # 1. สถานะ: ใช้ Dropdown เหมือนเดิม แต่ปรับ Style
    status = forms.ChoiceField(
        choices=Survey.Status.choices,
        widget=forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:ring-[#27693d] focus:border-[#27693d]'}),
        initial=Survey.Status.DRAFT,
        label="สถานะ"
    )

    class Meta:
        model = Survey
        # 2. ฟิลด์ที่ใช้: ตัด service_group และ version_number ออก (Version ค่อยไปเซ็ตใน View)
        fields = [
            'title_th', 'title_en', 'description', 
            'service_point', 'status'
        ]
        labels = {
            'title_th': 'ชื่อแบบสอบถาม (TH)',
            'title_en': 'ชื่อแบบสอบถาม (EN)',
            'description': 'คำอธิบาย',
            'service_point': 'จุดบริการ',
            'status': 'สถานะ'
        }
        widgets = {
            'title_th': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:ring-[#27693d] focus:border-[#27693d]', 'placeholder': 'ระบุชื่อภาษาไทย'}),
            'title_en': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:ring-[#27693d] focus:border-[#27693d]', 'placeholder': 'ระบุชื่อภาษาอังกฤษ'}),
            'description': forms.Textarea(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:ring-[#27693d] focus:border-[#27693d]', 'rows': 3, 'placeholder': 'รายละเอียดเพิ่มเติม (ถ้ามี)'}),
            'service_point': forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-md p-2 focus:ring-[#27693d] focus:border-[#27693d]'}),
        }

    # 3. รับ User เข้ามาเพื่อกรองจุดบริการ
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ถ้ามีการส่ง User เข้ามา ให้กรอง Dropdown 'service_point'
        if user:
            # แสดงเฉพาะจุดบริการที่ Manager คนนี้ดูแล (managed_points)
            self.fields['service_point'].queryset = user.managed_points.all().order_by('name')
            self.fields['service_point'].empty_label = "-- เลือกจุดบริการ --"

class ManagerQuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['order', 'text_th', 'text_en', 'question_type', 'is_required']
        
        widgets = {
            'text_th': forms.Textarea(attrs={
                'rows': 2, 
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm px-3 py-2 border'
            }),
            'text_en': forms.Textarea(attrs={
                'rows': 2, 
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm px-3 py-2 border'
            }),
            'question_type': forms.RadioSelect(), 
            'order': forms.NumberInput(attrs={
                'class': 'mt-1 block w-20 border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm px-3 py-2 border'
            }),
            'is_required': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'
            }),
        }
        
        labels = {
            'order': 'ลำดับ', 
            'text_th': 'คำถาม (TH)', 
            'text_en': 'คำถาม (EN)', 
            'question_type': 'ประเภทคำถาม', 
            'is_required': 'บังคับตอบ',
        }