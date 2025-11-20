from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Survey, Question, ServiceGroup, ServicePoint

# --- 1. Survey Form ---

class SurveyForm(forms.ModelForm):
    service_group = forms.ModelChoiceField(
        queryset=ServiceGroup.objects.all().order_by('name'),
        required=False,
        label="กลุ่มภารกิจ",
        widget=forms.Select(attrs={'id': 'id_group_filter'})
    )
    
    # เปลี่ยนจาก RadioSelect เป็น Select (Dropdown)
    status = forms.ChoiceField(
        choices=Survey.Status.choices,
        widget=forms.Select(attrs={'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}), 
        initial=Survey.Status.DRAFT,
        label="สถานะ"
    )

    class Meta:
        model = Survey
        fields = [
            'title_th', 'title_en', 'description',    
            'version_number', 'service_group', 'service_point', 'status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}), 
        }
        labels = {
            'title_th': 'ชื่อแบบสอบถาม (TH)',
            'title_en': 'ชื่อแบบสอบถาม (EN)', 
            'description': 'คำอธิบาย',      
            'service_point': 'จุดบริการ', 
            'version_number': 'เวอร์ชัน',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # โหลดจุดบริการทั้งหมดมารอไว้เสมอ (แก้ Error Validation)
        self.fields['service_point'].queryset = ServicePoint.objects.all().order_by('name')

        if self.instance.pk and self.instance.service_point:
            self.fields['service_group'].initial = self.instance.service_point.group

        self.fields['version_number'].disabled = True

# --- 2. Question Form ---
class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['survey', 'order', 'text_th', 'text_en', 'question_type', 'is_required']
        widgets = {
            'survey': forms.HiddenInput(),
            'text_th': forms.Textarea(attrs={'rows': 3}),
            'text_en': forms.Textarea(attrs={'rows': 3}),
            'question_type': forms.RadioSelect(choices=Question.QuestionType.choices),
            'order': forms.NumberInput(attrs={'style': 'width: 100px'}),
        }
        labels = {
            'order': 'ลำดับ', 'text_th': 'คำถาม (TH)', 'text_en': 'คำถาม (EN)', 
            'question_type': 'ประเภทคำถาม', 'is_required': 'บังคับตอบ',
        }

# --- 3. Other Forms ---
class ServiceGroupForm(forms.ModelForm):
    class Meta:
        model = ServiceGroup
        fields = ['name'] 
        labels = { 'name': 'ชื่อกลุ่มภารกิจ' }

class ServicePointForm(forms.ModelForm):
    class Meta:
        model = ServicePoint
        fields = ['group', 'code', 'name', 'managers']
        widgets = { 'managers': forms.CheckboxSelectMultiple }
        labels = { 'group': 'กลุ่มภารกิจ', 'code': 'รหัส', 'name': 'ชื่อจุดบริการ', 'managers': 'ผู้ดูแล' }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].queryset = ServiceGroup.objects.all().order_by('name')

class ManagerCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = { 'username': 'ชื่อผู้ใช้', 'first_name': 'ชื่อจริง', 'last_name': 'นามสกุล', 'email': 'อีเมล' }

class ManagerEditForm(UserChangeForm):
    password = None
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = { 'username': 'ชื่อผู้ใช้', 'first_name': 'ชื่อจริง', 'last_name': 'นามสกุล', 'email': 'อีเมล', 'is_active': 'สถานะ' }