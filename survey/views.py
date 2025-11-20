import logging 
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.views.generic import ListView, CreateView, UpdateView, TemplateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required,user_passes_test
from django.utils import timezone 
from django.contrib import messages
from django.db.models import Count, Q , Avg
from django.db import transaction
from django.contrib.auth.models import User, Group 
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from datetime import timedelta , datetime
from openpyxl.utils import get_column_letter
# Import แบบ Explicit เพื่อป้องกัน NameError
from .forms import (
    SurveyForm, QuestionForm, ServiceGroupForm, ServicePointForm, 
    ManagerCreateForm, ManagerEditForm
)
from .models import * 
import openpyxl
import csv
import json

# สร้าง Logger Instance
logger = logging.getLogger(__name__)

# --- Auxiliary Functions ---

def is_superuser(user):
    return user.is_superuser

def get_summary_context():
    return {
        'total_service_points': ServicePoint.objects.count(),
        'total_service_groups': ServiceGroup.objects.count(),
    }

def _get_point_map():
    """สร้างแผนที่ (JSON) ของ {Group: [Points]} สำหรับ Dropdown 2 ชั้น"""
    point_map = {}
    groups = ServiceGroup.objects.prefetch_related('service_points')
    
    for group in groups:
        point_map[group.id] = [
            {'id': point.id, 'name': point.name}
            for point in group.service_points.all().order_by('name') 
        ]
    return point_map

# --- Mixins ---

class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

# --- General Views ---

@login_required
def index(request):
    return render(request, "index.html")

def Home(request) :
    return render(request, 'survey/home.html')

# --- Dashboard View ---

@login_required
def dashboard_view(request):
    user = request.user
    base_service_points = ServicePoint.objects.all()
    managers_list = User.objects.none() 
    
    if user.is_authenticated:
        if not user.is_superuser:
            base_service_points = user.managed_points.all()
            managers_list = User.objects.filter(id=user.id).prefetch_related('managed_points')
        else:
            try:
                managers_group = Group.objects.get(name='Managers') 
                managers_list = managers_group.user_set.all().prefetch_related('managed_points')
            except Group.DoesNotExist:
                managers_list = User.objects.none()

    # A2: กรองตามวันที่ (Date Filter)
    today = timezone.now().date()
    start_date_default = today - timedelta(days=today.weekday()) # จันทร์
    end_date_default = start_date_default + timedelta(days=6) # อาทิตย์
    
    end_date_str = request.GET.get('end_date', end_date_default.strftime('%Y-%m-%d'))
    start_date_str = request.GET.get('start_date', start_date_default.strftime('%Y-%m-%d'))
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        start_date = start_date_default
        end_date = end_date_default
        
    end_date_for_query = end_date + timedelta(days=1)
    
    # --- B. สร้าง Queryset หลักที่ "กรองแล้ว" ---
    filtered_responses_for_charts_and_ticker = Response.objects.filter(
        service_point__in=base_service_points, 
        submitted_at__gte=start_date, 
        submitted_at__lt=end_date_for_query 
    )

    # --- C. คำนวณข้อมูล ---
    total_active_questions = Question.objects.filter(
        survey__status=Survey.Status.ACTIVE
    ).count()
    total_responses = filtered_responses_for_charts_and_ticker.count()

    # กรองโดยใช้ 'filtered_responses_for_charts_and_ticker'
    all_service_points_with_counts = base_service_points.annotate(
        response_count=Count('response', filter=Q(response__in=filtered_responses_for_charts_and_ticker))
    ).order_by('-response_count')

    # Card 3: กราฟแท่งรายสัปดาห์ (ซ้ายกลาง)
    date_labels = []
    day_counts_dict = {}
    current_date = start_date
    while current_date <= end_date:
        date_labels.append(current_date.strftime('%a')) 
        day_counts_dict[current_date] = 0
        current_date += timedelta(days=1)

    response_times = filtered_responses_for_charts_and_ticker.values_list('submitted_at', flat=True)

    for submitted_at_utc in response_times:
        local_time = timezone.localtime(submitted_at_utc)
        date_only = local_time.date() 
        if date_only in day_counts_dict:
            day_counts_dict[date_only] += 1
    bar_data_weekly = [day_counts_dict[day] for day in sorted(day_counts_dict.keys())]

    pie_data_all = base_service_points.annotate(
        response_count=Count('response', filter=Q(response__in=filtered_responses_for_charts_and_ticker))
    ).filter(response_count__gt=0).order_by('-response_count')
    pie_labels = [sp.name for sp in pie_data_all]
    pie_data = [sp.response_count for sp in pie_data_all]

    recent_feedback = ResponseAnswer.objects.filter(
        response__in=filtered_responses_for_charts_and_ticker, 
        question__question_type='TEXTAREA'
    ).exclude(
        Q(answer_rating__isnull=True) & 
        (Q(answer_text__isnull=True) | Q(answer_text__exact=''))
    ).select_related(
        'response__service_point'
    ).order_by('-response__submitted_at')[:5]
    
    # --- D. ส่งข้อมูลทั้งหมดไปที่ Template ---
    context = {
        'total_responses': total_responses,
        'total_service_points_in_view': base_service_points.count(),
        'total_active_questions': total_active_questions,
        'all_service_points_with_counts': all_service_points_with_counts,
        'bar_labels_weekly': json.dumps(date_labels),
        'bar_data_weekly': json.dumps(bar_data_weekly),
        'pie_labels': json.dumps(pie_labels),
        'pie_data': json.dumps(pie_data),
        'managers_list': managers_list,
        'recent_feedback': recent_feedback,
        'start_date': start_date_str,
        'end_date': end_date_str,
    }

    return render(request, 'survey/dashboard.html', context)

# ========== 1. Service Point Views (จุดบริการ) ==========

@login_required
@user_passes_test(is_superuser)
def service_point_list_view(request):
    queryset = ServicePoint.objects.select_related('group').prefetch_related('managers').order_by('code')
    
    search_query = request.GET.get('q', '')
    group_id = request.GET.get('group_id', '')

    if search_query:
        queryset = queryset.filter(Q(name__icontains=search_query) | Q(code__icontains=search_query))
    
    if group_id:
        queryset = queryset.filter(group_id=group_id)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    groups = ServiceGroup.objects.annotate(point_count=Count('service_points')).order_by('name')

    context = {
        'title': 'จัดการจุดบริการและกลุ่มภารกิจ',
        'page_obj': page_obj,
        'all_groups': ServiceGroup.objects.all().order_by('name'),
        'search_query': search_query,
        'group_id': group_id,
        'groups': groups, 
    }
    context.update(get_summary_context())
    return render(request, 'survey/service_point_list.html', context)

@login_required
@user_passes_test(is_superuser)
def service_point_create_view(request):
    if request.method == 'POST':
        form = ServicePointForm(request.POST)
        if form.is_valid():
            point = form.save()
            messages.success(request, f'เพิ่มจุดบริการ "{point.name}" สำเร็จ')
            return redirect('survey:service_point_list')
    else:
        form = ServicePointForm()

    context = {
        'title': 'เพิ่มจุดบริการใหม่',
        'form': form,
    }
    context.update(get_summary_context())
    return render(request, 'survey/service_point_form.html', context)

@login_required
@user_passes_test(is_superuser)
def service_point_edit_view(request, pk):
    point = get_object_or_404(ServicePoint, pk=pk)
    if request.method == 'POST':
        form = ServicePointForm(request.POST, instance=point)
        if form.is_valid():
            form.save()
            messages.success(request, f'อัปเดตจุดบริการ "{point.name}" สำเร็จ')
            return redirect('survey:service_point_list')
    else:
        form = ServicePointForm(instance=point)

    context = {
        'title': f'แก้ไขจุดบริการ: {point.name}',
        'form': form,
        'point': point,
    }
    context.update(get_summary_context())
    return render(request, 'survey/service_point_form.html', context)

@login_required
@user_passes_test(is_superuser)
def service_point_delete_view(request, pk):
    point = get_object_or_404(ServicePoint, pk=pk)
    try:
        point.delete()
        messages.success(request, f'ลบจุดบริการ "{point.name}" สำเร็จ')
    except Exception as e:
        messages.error(request, f'เกิดข้อผิดพลาดในการลบ: {e}')
    return redirect('survey:service_point_list')

# ========== 2. Service Group Views (กลุ่มภารกิจ) ==========
@login_required
@user_passes_test(is_superuser)
def service_group_create_view(request):
    if request.method == 'POST':
        form = ServiceGroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            messages.success(request, f'เพิ่มกลุ่มภารกิจ "{group.name}" สำเร็จ')
            return redirect('survey:service_point_list') 
    else:
        form = ServiceGroupForm()

    context = {
        'title': 'เพิ่มกลุ่มภารกิจใหม่',
        'form': form,
    }
    context.update(get_summary_context())
    return render(request, 'survey/service_group_form.html', context)

@login_required
@user_passes_test(is_superuser)
def service_group_edit_view(request, pk):
    group = get_object_or_404(ServiceGroup, pk=pk)
    if request.method == 'POST':
        form = ServiceGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f'อัปเดตกลุ่มภารกิจ "{group.name}" สำเร็จ')
            return redirect('survey:service_point_list') 
    else:
        form = ServiceGroupForm(instance=group)

    context = {
        'title': f'แก้ไขกลุ่มภารกิจ: {group.name}',
        'form': form,
        'group': group,
    }
    context.update(get_summary_context())
    return render(request, 'survey/service_group_form.html', context)

@login_required
@user_passes_test(is_superuser)
def service_group_delete_view(request, pk):
    group = get_object_or_404(ServiceGroup, pk=pk)
    if group.service_points.exists():
        messages.error(request, f'ไม่สามารถลบ "{group.name}" ได้ เพราะยังมีจุดบริการอยู่ในกลุ่มนี้')
        return redirect('survey:service_point_list')
        
    try:
        group.delete()
        messages.success(request, f'ลบกลุ่มภารกิจ "{group.name}" สำเร็จ')
    except Exception as e:
        messages.error(request, f'เกิดข้อผิดพลาดในการลบ: {e}')
    return redirect('survey:service_point_list')

##ส่วนเพิ่มผู้ดูแล
def get_manager_summary_context():
    manager_query = User.objects.filter(is_superuser=False)
    total_managers = manager_query.count()
    total_service_points = ServicePoint.objects.count()
    total_service_groups = ServiceGroup.objects.count() 
    all_groups = ServiceGroup.objects.all().order_by('name')
    manager_ids = set(manager_query.values_list('id', flat=True))
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    online_manager_ids = []

    for session in sessions:
        data = session.get_decoded()
        user_id = data.get('_auth_user_id', None)
        if user_id and int(user_id) in manager_ids:
            online_manager_ids.append(int(user_id))
    
    online_managers = len(set(online_manager_ids))

    all_points = ServicePoint.objects.all().values('id', 'group_id')
    service_point_map = {
        sp['id']: sp['group_id'] if sp['group_id'] is not None else 'none' 
        for sp in all_points
    }

    return {
        'total_managers': total_managers,
        'total_service_points': total_service_points,
        'total_service_groups': total_service_groups,
        'online_managers': online_managers, 
        'service_groups': all_groups, 
        'service_point_group_map': json.dumps(service_point_map)
    }

@login_required 
@user_passes_test(is_superuser) 
def manager_list_view(request):
    query = request.GET.get('q', '')
    manager_list_query = User.objects.filter(is_superuser=False).prefetch_related('managed_points').order_by('username')
    if query:
        manager_list_query = manager_list_query.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )

    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    online_user_ids = []
    for session in sessions:
        data = session.get_decoded()
        user_id = data.get('_auth_user_id', None)
        if user_id:
            online_user_ids.append(int(user_id))
    
    online_user_ids = set(online_user_ids) 
    context = {
        'managers': manager_list_query, 
        'search_query': query,
        'online_user_ids': online_user_ids,
    }
    context.update(get_manager_summary_context()) 
    return render(request, 'survey/manager_list.html', context)

@login_required
@user_passes_test(is_superuser)
def manager_create_view(request):
    if request.method == 'POST':
        form = ManagerCreateForm(request.POST) 
        if form.is_valid():
            user = form.save()
            messages.success(request, f'สร้างผู้ดูแล "{user.username}" สำเร็จ')
            return redirect('survey:manager_list')
    else:
        form = ManagerCreateForm() 
        
    context = {
        'form': form,
        'title': 'เพิ่มข้อมูลผู้ดูแล',
    }
    context.update(get_manager_summary_context()) 
    return render(request, 'survey/manager_form.html', context)

@login_required
@user_passes_test(is_superuser)
def manager_edit_view(request, pk):
    manager = get_object_or_404(User, pk=pk, is_superuser=False)
    
    if request.method == 'POST':
        form = ManagerEditForm(request.POST, instance=manager) 
        if form.is_valid():
            manager = form.save() 
            messages.success(request, f'อัปเดตข้อมูล "{manager.username}" สำเร็จ')
            return redirect('survey:manager_list')
    else:
        form = ManagerEditForm(instance=manager) 
        
    context = {
        'form': form,
        'manager': manager,
        'title': f'แก้ไขผู้ดูแล: {manager.username}',
    }
    context.update(get_manager_summary_context()) 
    return render(request, 'survey/manager_form.html', context)

@login_required
@user_passes_test(is_superuser)
def manager_delete_view(request, pk):
    manager = get_object_or_404(User, pk=pk, is_superuser=False)
    try:
        manager_name = manager.username
        manager.delete()
        messages.success(request, f'ลบผู้ดูแล "{manager_name}" สำเร็จ')
    except Exception as e:
        messages.error(request, f'เกิดข้อผิดพลาด: {e}')
    return redirect('survey:manager_list')

# --- CRUD: Survey ---

@login_required
@user_passes_test(is_superuser)
def survey_list_view(request):
    """
    หน้าแสดงรายการแบบสอบถาม + Modal สำหรับสร้างใหม่
    """
    # 1. ดึงรายการ Survey ทั้งหมด
    surveys = Survey.objects.annotate(
        question_count=Count('questions')
    ).select_related(
        'service_point', 
        'service_point__group'
    ).order_by('-created_at')

    show_modal = False # Flag ควบคุมการเปิด Modal (กรณี Error)

    # 2. Handle การสร้าง Survey ใหม่ (POST)
    if request.method == 'POST':
        form = SurveyForm(request.POST)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.created_by_user = request.user
            survey.save()
            
            messages.success(request, "สร้างแบบสอบถามเรียบร้อยแล้ว")
            return redirect('survey:survey_list') # Refresh หน้าเพื่อเคลียร์ Form
        else:
            show_modal = True # ถ้า Error ให้เปิด Modal ค้างไว้
            messages.error(request, "เกิดข้อผิดพลาด กรุณาตรวจสอบข้อมูล")
    else:
        # เตรียมฟอร์มเปล่า
        form = SurveyForm()

    # 3. เตรียม Context (รวมถึง JSON Map สำหรับ Dropdown)
    context = {
        'surveys': surveys,
        'form': form,
        'show_modal': show_modal,
        'point_map_json': json.dumps(_get_point_map()), # ส่งแผนที่จุดบริการไปให้ JS
        'page_title': 'จัดการแบบสอบถาม'
    }

    return render(request, 'survey/survey_list.html', context)


class SurveyUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Survey
    form_class = SurveyForm
    template_name = 'survey/survey_form.html' 
    success_url = reverse_lazy('survey:survey_list')

    # === Logic แก้ไขค่าสถานะก่อนโหลดฟอร์ม (พร้อม Logger) ===
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        valid_statuses = [choice[0] for choice in Survey.Status.choices]
        safe_status = Survey.Status.DRAFT
        
        # --- DEBUG LOGGING START ---
        logger.warning(f"\n--- SurveyUpdateView Debug (PK: {obj.pk}) ---")
        logger.warning(f"1. Status loaded from DB: '{obj.status}' (Type: {type(obj.status)})")
        logger.warning(f"2. Valid choices: {valid_statuses}")
        # --- DEBUG LOGGING END ---
        
        is_invalid = obj.status not in valid_statuses
        
        if obj.status is None or obj.status == '' or is_invalid:
            logger.warning(f"3. Correction triggered! Invalid status. Original: '{obj.status}'")
            obj.status = safe_status
            try:
                obj.save(update_fields=['status']) 
                messages.warning(self.request, f"สถานะเดิม ({obj.status}) ไม่ถูกต้อง แก้ไขเป็น '{safe_status}'")
                logger.warning(f"4. Status corrected to: '{safe_status}'")
            except Exception as e:
                logger.error(f"FATAL ERROR: Could not correct status. Error: {e}") 
        else:
            logger.warning("3. Status is valid.")

        return obj

    def form_valid(self, form):
        messages.success(self.request, "แก้ไขข้อมูลเรียบร้อยแล้ว")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"แก้ไข: {self.object.title_th}"
        context['btn_text'] = "บันทึกการแก้ไข"
        context['cancel_url'] = reverse_lazy('survey:survey_list')
        context['point_map_json'] = json.dumps(_get_point_map())
        return context
    
class SurveyDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Survey
    template_name = 'survey/survey_confirm_delete.html'
    success_url = reverse_lazy('survey:survey_list')


# --- Question Views ---

@login_required
@user_passes_test(lambda u: u.is_superuser)
def question_list_view(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id)
    questions = survey.questions.all().order_by('order')
    
    # === ส่วนที่เพิ่ม: จัดการการสร้างคำถามในหน้านี้เลย ===
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.survey = survey
            question.created_by_user = request.user
            question.save()
            
            messages.success(request, 'เพิ่มคำถามสำเร็จ')
            # Redirect กลับมาหน้าเดิม (เพื่อล้างค่า POST)
            return redirect('survey:question_list', survey_id=survey.id)
        else:
            # ถ้า Error ให้เปิด Modal ค้างไว้
            show_modal = True
    else:
        # เตรียมฟอร์มเปล่าสำหรับใส่ใน Modal
        last_order = survey.questions.all().count() + 1
        form = QuestionForm(initial={'order': last_order, 'survey': survey})
        show_modal = False
    # ==================================================

    return render(request, 'survey/question_list.html', {
        'survey': survey,
        'questions': questions,
        'form': form,           # ส่งฟอร์มไปที่ Template
        'show_modal': show_modal # ส่ง Flag เพื่อบอกว่าควรเปิด Modal ไหม (กรณี Error)
    })

class QuestionUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Question
    form_class = QuestionForm
    # ไม่ต้องใช้ template_name แล้วเพราะเราจะ redirect กลับ
    # template_name = 'survey/question_form.html' 
    
    def form_valid(self, form):
        messages.success(self.request, "แก้ไขคำถามเรียบร้อยแล้ว")
        return super().form_valid(form)

    def form_invalid(self, form):
        # กรณี Error เราต้อง Redirect กลับไปหน้า List พร้อม Error (ยากนิดนึงถ้าไม่ใช้ AJAX)
        # แต่วิธีง่ายสุดคือให้มัน Render หน้า List เดิม แต่เปิด Modal
        # เพื่อความง่าย เราจะใช้การ Redirect กลับไปหน้า List แล้วแจ้งเตือน
        messages.error(self.request, "เกิดข้อผิดพลาดในการแก้ไข กรุณาลองใหม่")
        return redirect('survey:question_list', survey_id=self.object.survey.id)

    def get_success_url(self):
        return reverse('survey:question_list', args=[self.object.survey.id])


class QuestionDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Question
    template_name = 'survey/survey_confirm_delete.html' 
    def get_success_url(self):
        messages.success(self.request, "ลบคำถามเรียบร้อยแล้ว")
        return reverse('survey:question_list', args=[self.object.survey.id])

# --- Kiosk Views ---

def kiosk_welcome_view(request, service_point_id):
    service_point = get_object_or_404(ServicePoint, id=service_point_id)
    
    if 'patient_info' in request.session:
        del request.session['patient_info']
        
    # [แก้ไขคืนชีพ] กรองเอาเฉพาะ Active
    active_survey = Survey.objects.filter(
        service_point=service_point, 
        status=Survey.Status.ACTIVE
    ).order_by('-id').first()

    if not active_survey:
        return render(request, 'kiosk/kiosk_welcome.html', {
            'service_point': service_point,
            'active_survey': None
        })
    
    if request.method == 'POST':
        return redirect('survey:kiosk_user_info', service_point_id=service_point.id)

    context = {
        'service_point': service_point,
        'active_survey': active_survey
    }
    return render(request, 'kiosk/kiosk_welcome.html', context)
        
    if request.method == 'POST':
        # ถ้ามีการกดปุ่ม (POST) ให้พาไปหน้ากรอกข้อมูลผู้ป่วย
        return redirect('survey:kiosk_user_info', service_point_id=service_point.id)
    
    print(f"DEBUG: สรุปผล -> เลือกแบบสอบถาม ID: {active_survey.id}")
    context = {
        'service_point': service_point,
        'active_survey': active_survey
    }
    return render(request, 'kiosk/kiosk_welcome.html', context)

def kiosk_user_info_view(request, service_point_id):
    service_point = get_object_or_404(ServicePoint, id=service_point_id)

    if request.method == 'POST':
        patient_info = {
            'patient_type': request.POST.get('patient_type'),
            'user_role': request.POST.get('user_role'),
            'benefit_plan': request.POST.get('benefit_plan'),
            'benefit_plan_other': request.POST.get('benefit_plan_other', ''), 
            'age_range': request.POST.get('age_range'),
            'gender': request.POST.get('patient_gender', 'NOT_SPECIFIED'),
        }
        request.session['patient_info'] = patient_info
        return redirect('survey:survey_display', service_point_id=service_point.id)
    
    # [แก้ไข] สร้างรายการตัวเลือกที่นี่ แล้วส่งไปที่ Template
    age_ranges = ["ต่ำกว่า 20 ปี", "20-39 ปี", "40-59 ปี", "60 ปีขึ้นไป"]

    context = { 
        'service_point': service_point,
        'age_ranges': age_ranges # ส่งค่าไป
    }
    return render(request, 'kiosk/kiosk_user_info.html', context)

def kiosk_thank_you_view(request, service_point_id):
    context = {'service_point_id': service_point_id}
    return render(request, 'kiosk/kiosk_thank_you.html', context)

def survey_display_view(request, service_point_id):
    service_point = get_object_or_404(ServicePoint, id=service_point_id)
    
    print(f"--- DEBUG DISPLAY VIEW (SP: {service_point.id}) ---")
    
    # 1. ลองหาตัวที่ Active ก่อน (ตามที่คุณต้องการ)
    active_survey = Survey.objects.filter(
        service_point=service_point,
        status=Survey.Status.ACTIVE
    ).order_by('-id').first()

    if active_survey:
        print(f"✅ เจอแบบสอบถาม ACTIVE: ID {active_survey.id} ({active_survey.title_th})")
    else:
        print("❌ ไม่เจอแบบสอบถาม ACTIVE... กำลังลองหาตัวล่าสุดที่เป็น DRAFT แทน...")
        
        # 2. ถ้าไม่เจอ (Fallback) -> เอาตัวล่าสุดมาเลย (กันหน้าจอขาว)
        active_survey = Survey.objects.filter(
            service_point=service_point
        ).order_by('-id').first()
        
        if active_survey:
            print(f"⚠️ เจอตัวสำรอง (Status: {active_survey.status}): ID {active_survey.id}")
        else:
            print("💀 ไม่เจออะไรเลยในจุดบริการนี้")

    if not active_survey:
        # ถ้าหาไม่เจอจริงๆ ค่อยยอมแพ้
        return render(request, 'kiosk/survey_display.html', {
            'service_point': service_point,
            'survey': None
        })
    
    context = {
        'service_point': service_point,
        'survey': active_survey,
    }
    return render(request, 'kiosk/survey_display.html', context)

def survey_submit_view(request, survey_id):
    if request.method != 'POST':
        return redirect('survey:kiosk_welcome', service_point_id=1) 
    
    survey = get_object_or_404(Survey, id=survey_id) 
    service_point_id = request.POST.get('service_point_id')
    service_point = get_object_or_404(ServicePoint, id=service_point_id)
    patient_info = request.session.get('patient_info', {})

    # [แก้ไข] เพิ่ม submitted_at=timezone.now() เพื่อบันทึกเวลาปัจจุบัน
    response = Response.objects.create(
        survey=survey, 
        service_point=service_point,
        patient_type=patient_info.get('patient_type'),
        user_role=patient_info.get('user_role'),
        benefit_plan=patient_info.get('benefit_plan'),
        benefit_plan_other=patient_info.get('benefit_plan_other'),
        age_range=patient_info.get('age_range'),
        gender=patient_info.get('gender'),
        submitted_at=timezone.now() # <--- เพิ่มบรรทัดนี้!
    )

    for key, value in request.POST.items():
        if key.startswith('q-'):
            if not value: continue
            try:
                question_id = key.split('-')[1]
                question = Question.objects.get(id=question_id)
                if question.question_type == 'RATING_5':
                    ResponseAnswer.objects.create(
                        response=response, 
                        question=question, 
                        answer_rating=int(value)
                    )
                elif question.question_type == 'TEXTAREA':
                    ResponseAnswer.objects.create(
                        response=response, 
                        question=question, 
                        answer_text=str(value)
                    )
            except (Question.DoesNotExist, ValueError): 
                continue 
    
    if 'patient_info' in request.session:
        del request.session['patient_info']

    return redirect('survey:kiosk_thank_you', service_point_id=service_point_id)

# --- Export Views ---

def get_filtered_data_for_export(request):
    user = request.user
    base_service_points = ServicePoint.objects.all()
    if user.is_authenticated and not user.is_superuser:
        managed_points = user.managed_points.all()
        base_service_points = base_service_points.filter(id__in=managed_points.values('id'))
    end_date_str = request.GET.get('end_date', timezone.now().strftime('%Y-%m-%d'))
    start_date_str = request.GET.get('start_date', (timezone.now() - timedelta(days=6)).strftime('%Y-%m-%d'))
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        start_date = (timezone.now() - timedelta(days=6)).date()
        end_date = timezone.now().date()
    end_date_for_query = end_date + timedelta(days=1)
    base_responses_filtered = Response.objects.filter(
        service_point__in=base_service_points,
        submitted_at__gte=start_date,
        submitted_at__lt=end_date_for_query
    )
    queryset = ResponseAnswer.objects.filter(
        response__in=base_responses_filtered
    ).select_related('response', 'response__service_point', 'question').order_by('response__submitted_at')
    return queryset

def export_responses_csv(request):
    response = HttpResponse(content_type='text/csv', headers={'Content-Disposition': 'attachment; filename="survey_responses.csv"'})
    response.write('\ufeff') 
    writer = csv.writer(response)
    writer.writerow(['Response ID', 'Service Point', 'Submitted At', 'Question (TH)', 'Question (EN)', 'Question Type', 'Answer Value'])
    queryset = get_filtered_data_for_export(request)
    for answer in queryset:
        writer.writerow([
            answer.response.id, answer.response.service_point.name, answer.response.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
            answer.question.text_content.get('th', ''), answer.question.text_content.get('en', ''),
            answer.question.get_question_type_display(), answer.answer_value
        ])
    return response

def export_responses_excel(request):
    queryset = get_filtered_data_for_export(request)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Responses"
    headers = ['Response ID', 'Service Point', 'Submitted At', 'Question (TH)', 'Question (EN)', 'Question Type', 'Answer Value']
    ws.append(headers)
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = openpyxl.styles.Font(bold=True)
        if col_num in [4, 5]: ws.column_dimensions[get_column_letter(col_num)].width = 40
        else: ws.column_dimensions[get_column_letter(col_num)].width = 20
    for answer in queryset:
        local_submitted_at = timezone.localtime(answer.response.submitted_at)       
        naive_submitted_at = local_submitted_at.replace(tzinfo=None)
        ws.append([
            answer.response.id, answer.response.service_point.name, naive_submitted_at, 
            answer.question.text_content.get('th', ''), answer.question.text_content.get('en', ''),
            answer.question.get_question_type_display(), answer.answer_value
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment; filename="survey_responses.xlsx"'})
    wb.save(response)
    return response

@login_required
@user_passes_test(is_superuser)
def assessment_results_view(request):
    # 1. รับค่า Filter
    group_id = request.GET.get('group_id')
    point_id = request.GET.get('point_id')
    score_filter = request.GET.get('score') # รับค่าช่วงคะแนน (เช่น "4-5")
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # 2. Queryset เริ่มต้น & คำนวณคะแนนเฉลี่ย
    responses = Response.objects.annotate(
        avg_score=Avg('answers__answer_rating')
    ).select_related('service_point', 'service_point__group').order_by('-submitted_at')
    
    # --- กรองตามคะแนน (Score Range) ---
    if score_filter:
        try:
            min_score, max_score = map(int, score_filter.split('-'))
            if max_score == 5:
                # กรณี 4-5 ให้รวม 5 ด้วย (<= 5)
                responses = responses.filter(avg_score__gte=min_score, avg_score__lte=max_score)
            else:
                # กรณีอื่น เช่น 1-2 ให้เป็น 1 <= x < 2
                responses = responses.filter(avg_score__gte=min_score, avg_score__lt=max_score)
        except ValueError:
            pass
    # ---------------------------------

    # กรองวันที่
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            responses = responses.filter(submitted_at__date__range=[start_date, end_date])
        except ValueError:
            pass
    
    # กรองกลุ่ม/จุดบริการ
    if group_id:
        responses = responses.filter(service_point__group_id=group_id)
    if point_id:
        responses = responses.filter(service_point_id=point_id)

    # 3. Stats
    total_assessments = responses.count()
    total_suggestions = ResponseAnswer.objects.filter(
        response__in=responses,
        question__question_type='TEXTAREA'
    ).exclude(answer_text='').count()

    # 4. Pagination
    paginator = Paginator(responses, 10) 
    page_obj = paginator.get_page(request.GET.get('page'))

    # 5. Suggestions List
    recent_suggestions = ResponseAnswer.objects.filter(
        response__in=responses,
        question__question_type='TEXTAREA'
    ).exclude(answer_text='').select_related('response', 'response__service_point').order_by('-id')[:10]

    # 6. Choices & Map
    groups = ServiceGroup.objects.all()
    # ไม่ต้องส่ง points ทั้งหมดแล้ว เพราะ JS จะจัดการตาม Group
    # แต่ส่งไว้เผื่อกรณีไม่ได้เลือก Group (หรือจะใช้ JS โหลดทั้งหมดก็ได้)
    points = ServicePoint.objects.all() 
    
    context = {
        'page_title': 'ผลการประเมิน',
        'total_assessments': total_assessments,
        'total_suggestions': total_suggestions,
        'page_obj': page_obj,
        'recent_suggestions': recent_suggestions,
        'groups': groups,
        'points': points,
        'point_map_json': json.dumps(_get_point_map()), # [สำคัญ] ส่ง Map ไปให้ JS
        'selected_group': int(group_id) if group_id else '',
        'selected_point': int(point_id) if point_id else '',
        'selected_score': score_filter,
        'start_date': start_date_str if start_date_str else '',
        'end_date': end_date_str if end_date_str else '',
    }
    return render(request, 'survey/assessment_results.html', context)


login_required
@user_passes_test(is_superuser)
def suggestion_list_view(request):
    # 1. รับค่า Filter (เหมือนหน้า Assessment)
    group_id = request.GET.get('group_id')
    point_id = request.GET.get('point_id')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    search_query = request.GET.get('q', '')

    # 2. Base Query: หาคำตอบที่เป็น TEXTAREA และไม่ว่าง
    suggestions = ResponseAnswer.objects.filter(
        question__question_type='TEXTAREA'
    ).exclude(answer_text='').select_related(
        'response', 
        'response__service_point', 
        'response__service_point__group'
    ).order_by('-response__submitted_at')
    
    # 3. Apply Filters
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            suggestions = suggestions.filter(response__submitted_at__date__range=[start_date, end_date])
        except ValueError:
            pass

    if group_id:
        suggestions = suggestions.filter(response__service_point__group_id=group_id)
    if point_id:
        suggestions = suggestions.filter(response__service_point_id=point_id)
    
    if search_query:
        suggestions = suggestions.filter(answer_text__icontains=search_query)

    # 4. Pagination
    paginator = Paginator(suggestions, 20) # หน้าละ 20 รายการ
    page_obj = paginator.get_page(request.GET.get('page'))

    # 5. Choices for Filter
    groups = ServiceGroup.objects.all()
    points = ServicePoint.objects.all()
    if group_id: points = points.filter(group_id=group_id)

    context = {
        'page_title': 'รายการข้อเสนอแนะทั้งหมด',
        'page_obj': page_obj,
        'groups': groups,
        'points': points,
        'selected_group': int(group_id) if group_id else '',
        'selected_point': int(point_id) if point_id else '',
        'start_date': start_date_str if start_date_str else '',
        'end_date': end_date_str if end_date_str else '',
        'search_query': search_query,
    }
    return render(request, 'survey/suggestion_list.html', context)

def _get_point_map():
    """สร้างแผนที่ (JSON) ของ {Group: [Points]} สำหรับ Dropdown 2 ชั้น"""
    point_map = {}
    groups = ServiceGroup.objects.prefetch_related('service_points')
    for group in groups:
        point_map[group.id] = [
            {'id': point.id, 'name': point.name}
            for point in group.service_points.all().order_by('name') 
        ]
    return point_map