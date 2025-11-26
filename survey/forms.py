from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Survey, Question, ServiceGroup, ServicePoint

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

class ManagerCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="รหัสผ่าน", 
        widget=forms.PasswordInput(attrs={'placeholder': 'กำหนดรหัสผ่าน'}),
        required=True
    )
    password2 = forms.CharField(
        label="ยืนยันรหัสผ่าน", 
        widget=forms.PasswordInput(attrs={'placeholder': 'ยืนยันรหัสผ่านอีกครั้ง'}),
        required=True
    )

    managed_points = forms.ModelMultipleChoiceField(
        label="จุดบริการที่รับผิดชอบ",
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

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(f"Username '{username}' ถูกใช้งานแล้ว กรุณาเปลี่ยนชื่อใหม่")
        return username

    def clean_password2(self):
        p1 = self.cleaned_data.get('password')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("รหัสผ่านทั้ง 2 ช่องไม่ตรงกัน")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        
        if commit:
            user.save()
            if 'managed_points' in self.cleaned_data:
                user.managed_points.set(self.cleaned_data['managed_points'])
                
        return user

class ManagerEditForm(forms.ModelForm):
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

    # (1) ดึงข้อมูลเดิมมาติ๊กใน Checkbox
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['managed_points'].initial = self.instance.managed_points.all()

    # (2) ตรวจสอบ Username ซ้ำ (แก้ไข NameError ตรงนี้ครับ)
    def clean_username(self):
        # ต้องประกาศตัวแปร username บรรทัดนี้ก่อนครับ
        username = self.cleaned_data.get('username')
        
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"Username '{username}' มีผู้ใช้งานอื่นใช้แล้ว")
            
        return username

    # (3) ตรวจสอบรหัสผ่าน
    def clean_password2(self):
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError("รหัสผ่านใหม่ 2 ช่องไม่ตรงกัน")
        return password2

    # (4) บันทึกข้อมูล
    def save(self, commit=True):
        user = super().save(commit=False) 
        
        # ถ้ากรอกรหัสใหม่มา ให้ตั้งรหัสใหม่
        new_password = self.cleaned_data.get('password')
        if new_password:
            user.set_password(new_password)
        
        if commit:
            user.save()
            # บันทึกจุดบริการ (รวมทั้งของเก่าและของใหม่ที่ส่งมาจากหน้าเว็บ)
            points = self.cleaned_data.get('managed_points')
            if points is not None:
                user.managed_points.set(points)
                
        return user