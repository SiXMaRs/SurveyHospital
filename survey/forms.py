from django.contrib import admin
from django import forms
from .models import *
from django.contrib.auth.models import User

def add_tailwind_classes(form):
    tailwind_class = "w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
    for field_name, field in form.fields.items():
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs.update({'class': tailwind_class, 'rows': 3})
        elif isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'h-5 w-5 text-blue-600 rounded border-gray-300 focus:ring-blue-500'})
            pass 
        else:
            field.widget.attrs.update({'class': tailwind_class})

class ServiceGroupForm(forms.ModelForm):
    """
    ฟอร์มสำหรับเพิ่ม/แก้ไข กลุ่มภารกิจ
    """
    class Meta:
        model = ServiceGroup
        fields = ['name']
        labels = {
            'name': 'ชื่อกลุ่มภารกิจ',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'เช่น กลุ่มงานการพยาบาล, กลุ่มงานทันตกรรม'}),
        }

class ServicePointForm(forms.ModelForm):
    """
    ฟอร์มสำหรับเพิ่ม/แก้ไข จุดบริการ
    """
    managers = forms.ModelMultipleChoiceField(
        label="ผู้ดูแล (Manager)",
        queryset=User.objects.filter(is_superuser=False, is_staff=True).order_by('username'),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = ServicePoint
        fields = ['name', 'code', 'group', 'managers']
        labels = {
            'name': 'ชื่อจุดบริการ',
            'code': 'รหัส Code (ห้ามซ้ำ)',
            'group': 'กลุ่มภารกิจ',
            'managers': 'ผู้ดูแลที่รับผิดชอบ',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'เช่น งานผู้ป่วยนอก, คลินิกเบาหวาน'}),
            'code': forms.TextInput(attrs={'placeholder': 'เช่น OPD, DM_CLINIC'}),
            'group': forms.Select(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].required = False

class ManagerCreateForm(forms.ModelForm):
    password = forms.CharField(label="Password", widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput, required=True)
    
    managed_points = forms.ModelMultipleChoiceField(
        label="จุดบริการที่รับผิดชอบ",
        # (สำคัญ!) ต้องดึง "ทั้งหมด" มาให้ JavaScript กรอง
        queryset=ServicePoint.objects.all().select_related('group'), 
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'password2', 'managed_points']
        labels = {
            'username': 'Username',
            'first_name': 'ชื่อจริง',
            'last_name': 'นามสกุล',
            'email': 'อีเมล',
        }

    # --- (นี่คือส่วนที่แก้ไข) ---
    def __init__(self, *args, **kwargs):
        # (ลบ request = kwargs.pop('request', None) ออก)
        super().__init__(*args, **kwargs)
        add_tailwind_classes(self)
        # (ลบการกรอง Queryset ทั้งหมดออกจาก __init__)
    # --- (จบส่วนแก้ไข) ---

    def clean_password2(self):
        # (โค้ด clean_password2 ... เหมือนเดิม)
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError("รหัสผ่าน 2 ช่องไม่ตรงกัน")
        return password2

    def save(self, commit=True):
        # (โค้ด save ... เหมือนเดิม)
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_staff = True
        if commit:
            user.save()
            points = self.cleaned_data.get('managed_points')
            if points:
                user.managed_points.set(points)
        return user

class ManagerEditForm(forms.ModelForm):
    # --- 1. ประกาศ Fields เหมือนเดิม (ถูกต้อง) ---
    password = forms.CharField(
        label="รหัสผ่านใหม่ (เว้นว่างถ้าไม่เปลี่ยน)", 
        widget=forms.PasswordInput(attrs={'placeholder': 'กรอกเฉพาะเมื่อต้องการเปลี่ยนรหัส'}),
        required=False
    )
    password2 = forms.CharField(
        label="ยืนยันรหัสผ่านใหม่", 
        widget=forms.PasswordInput(attrs={'placeholder': 'ยืนยันรหัสผ่าน'}),
        required=False
    )
    managed_points = forms.ModelMultipleChoiceField(
        label="จุดบริการที่รับผิดชอบ",
        queryset=ServicePoint.objects.all().select_related('group'),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email'] 
        labels = {
            'username': 'Username',
            'first_name': 'ชื่อจริง',
            'last_name': 'นามสกุล',
            'email': 'อีเมล',
        }

    # (ฟังก์ชัน __init__ และ clean_password2 - ถูกต้องแล้ว)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # add_tailwind_classes(self) # (ใส่กลับไปถ้าคุณมีไฟล์นี้)

    def clean_password2(self):
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError("รหัสผ่านใหม่ 2 ช่องไม่ตรงกัน")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False) 
        new_password = self.cleaned_data.get('password')
        if new_password:
            user.set_password(new_password)

        if commit:
            user.save()

        if 'managed_points' in self.data:
            points = self.cleaned_data.get('managed_points')
            
            if commit:
                user.managed_points.set(points)
        return user
    
# --- Form 1: Survey ---
class SurveyForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = ['title_th', 'title_en', 'description']
        labels = {
            'title_th': 'ชื่อแบบสอบถาม (TH)', 
            'title_en': 'ชื่อแบบสอบถาม (EN) (ไม่บังคับ)',
            'description': 'คำอธิบาย'
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) 
        add_tailwind_classes(self)
        
    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if user and not instance.created_by_user:
            instance.created_by_user = user
        if commit:
            instance.save()
        return instance

# --- Form 2: SurveyVersion (ตัวสำคัญ) ---
class SurveyVersionForm(forms.ModelForm):
    service_points = forms.ModelMultipleChoiceField(
        queryset=ServicePoint.objects.all().order_by('name'),
        required=False,
        label="เลือกจุดบริการที่ใช้เวอร์ชันนี้",
        widget=forms.CheckboxSelectMultiple 
    )

    class Meta:
        model = SurveyVersion
        fields = ['survey', 'version_number', 'status', 'service_points']
        labels = {
            'survey': 'แม่แบบ (Survey)',
            'version_number': 'ชื่อเวอร์ชัน (เช่น v1.0, ปี 2568)',
            'status': 'สถานะ',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_tailwind_classes(self)
        
        if self.instance.pk:
            self.fields['service_points'].initial = self.instance.service_points.all()

    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if user and not instance.created_by_user:
            instance.created_by_user = user
        if commit:
            instance.save()
            selected_points = self.cleaned_data.get('service_points')
            # ล้างข้อมูลเก่าของเวอร์ชันนี้ทิ้งก่อน
            SurveyServicePoint.objects.filter(survey_version=instance).delete()
            # สร้างข้อมูลใหม่ทีละจุด
            if selected_points:
                new_relations = []
                for sp in selected_points:
                    new_relations.append(
                        SurveyServicePoint(survey_version=instance, service_point=sp)
                    )
                SurveyServicePoint.objects.bulk_create(new_relations)          
        return instance

# --- Form 3: Question ---
class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['question_type', 'text_th', 'text_en', 'order', 'is_required']
        labels = {
            'question_type': 'ประเภทคำถาม',
            'text_th': 'คำถาม (ภาษาไทย)',
            'text_en': 'คำถาม (ภาษาอังกฤษ) (ไม่บังคับ)',
            'order': 'ลำดับข้อ',
            'is_required': 'บังคับตอบ',
        }
        widgets = {
            'text_th': forms.Textarea(attrs={'rows': 2}),
            'text_en': forms.Textarea(attrs={'rows': 2}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_tailwind_classes(self)
    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        if user and not instance.created_by_user:
            instance.created_by_user = user
        if commit:
            instance.save()
        return instance