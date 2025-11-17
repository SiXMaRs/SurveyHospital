from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.views.generic import ListView, CreateView, UpdateView, TemplateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required,user_passes_test
from django.utils import timezone 
from django.contrib import messages
from django.db.models import Count, Q
from django.db import transaction
from django.contrib.auth.models import User, Group 
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from datetime import timedelta , datetime
from openpyxl.utils import get_column_letter
from .forms import *
from .models import *
import json
import openpyxl
import csv

@login_required
def index(request):
    return render(request, "index.html")

def Home(request) :
    return render(request, 'survey/home.html')

##หน้าDashboard
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
        survey_version__status='ACTIVE'
    ).distinct().count()
    total_responses = filtered_responses_for_charts_and_ticker.count()

    # กรองโดยใช้ 'filtered_responses_for_charts_and_ticker'
    # เพื่อให้จำนวน response_count ตรงกับวันที่ที่เลือก
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
    ).exclude(answer_value__exact='').select_related(
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


def is_superuser(user):
    return user.is_superuser

def get_summary_context():
    return {
        'total_service_points': ServicePoint.objects.count(),
        'total_service_groups': ServiceGroup.objects.count(),
    }

# ========== 1. Service Point Views (จุดบริการ) ==========
def get_summary_context():
    return {
        'total_service_points': ServicePoint.objects.count(),
        'total_service_groups': ServiceGroup.objects.count(),
    }

@login_required
@user_passes_test(is_superuser)
def service_point_list_view(request):
    """
    หน้า List แสดงจุดบริการ และ กลุ่มภารกิจ (ในหน้าเดียว)
    """
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

    # --- 2. Get Service Group Data ---
    groups = ServiceGroup.objects.annotate(point_count=Count('service_points')).order_by('name')

    # --- 3. Build Context ---
    context = {
        'title': 'จัดการจุดบริการและกลุ่มภารกิจ',
        'page_obj': page_obj,
        'all_groups': ServiceGroup.objects.all().order_by('name'), # For filter dropdown
        'search_query': search_query,
        'group_id': group_id,
        'groups': groups, 
    }
    context.update(get_summary_context())
    return render(request, 'survey/service_point_list.html', context) # (ใช้ Template เดิม)

@login_required
@user_passes_test(is_superuser)
def service_point_create_view(request):
    """
    หน้าฟอร์มสำหรับ "เพิ่ม" จุดบริการ
    """
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
    """
    หน้าฟอร์มสำหรับ "แก้ไข" จุดบริการ
    """
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
    """
    หน้าฟอร์มสำหรับ "เพิ่ม" กลุ่มภารกิจ
    """
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
    """
    หน้าฟอร์มสำหรับ "แก้ไข" กลุ่มภารกิจ
    """
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
        # 3. ถ้า ID ใน Session เป็น Manager ให้เก็บไว้
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
        'online_managers': online_managers, # <-- (ค่านี้ถูกต้องแล้ว)
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
        # (แก้ตรงนี้: ลบ request=request ออก)
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
        # (แก้ตรงนี้: ลบ request=request ออก)
        # (instance=manager ถูกต้องแล้ว มันจะติ๊กช่องให้เอง)
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

def survey_display_view(request, pk):
    """
    (แก้ไข) View นี้สำหรับแสดงหน้า Kiosk (ที่ไม่มี Section)
    """
    service_point = get_object_or_404(ServicePoint, id=pk)
    active_version = service_point.survey_versions.filter(
        status=SurveyVersion.Status.ACTIVE
    ).order_by('-id').first()
    # (ถ้าไม่เจอเวอร์ชันที่ Active เลย ก็ไม่ต้องแสดง)
    if not active_version:
        return render(request, 'survey/survey_display.html', {
            'service_point': service_point,
            'active_version': None
        })
    context = {
        'service_point': service_point,
        'active_version': active_version,
    }
    return render(request, 'survey/survey_display.html', context)


def survey_submit_view(request, version_id):
    if request.method != 'POST':
        return redirect('/') 
    
    survey_version = get_object_or_404(SurveyVersion, id=version_id)
    # --- ดึง service_point_id จากฟอร์มที่ซ่อนไว้ ---
    service_point_pk = request.POST.get('service_point_id')
    new_response = Response.objects.create(
        survey_version=survey_version,
        service_point_id=service_point_pk,
        submitted_at=timezone.now(),
    )

    for key, value in request.POST.items():
        if key.startswith('question_'):
            try:
                question_id = key.split('_')[1]
                question = Question.objects.get(id=question_id)

                if question.question_type in ['RATING_5', 'TEXTAREA']:
                    ResponseAnswer.objects.create(
                        response=new_response,
                        question_id=question_id,
                        option_id=None,
                        answer_value=value
                    )
            except:
                pass 
    context = {
        'service_point_pk': service_point_pk
    }
    return render(request, 'survey/thankyou.html', context)


def get_filtered_data_for_export(request):
    """(ฟังก์ชันช่วย) ดึงข้อมูลดิบ (Raw Data) ตาม Filterเพื่อใช้ร่วมกันทั้ง CSV และ Excel"""
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
    # --- 2. ดึงข้อมูลดิบ (Raw Data) ---
    # นี่คือข้อมูลที่เราจะ Export: "คำตอบย่อย" ทั้งหมด
    queryset = ResponseAnswer.objects.filter(
        response__in=base_responses_filtered
    ).select_related(
        'response',                 
        'response__service_point',  
        'question'                 
    ).order_by('response__submitted_at')
    return queryset

def export_responses_csv(request):
    """
    ส่งออกข้อมูลเป็น CSV
    """
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="survey_responses.csv"'},
    )
    response.write('\ufeff') 
    writer = csv.writer(response)
    
    # 1. เขียนหัวตาราง (Header)
    writer.writerow([
        'Response ID',
        'Service Point',
        'Submitted At',
        'Question (TH)',
        'Question (EN)',
        'Question Type',
        'Answer Value'
    ])
    # 2. ดึงข้อมูล
    queryset = get_filtered_data_for_export(request)
    # 3. เขียนข้อมูล (Data)
    for answer in queryset:
        writer.writerow([
            answer.response.id,
            answer.response.service_point.name,
            answer.response.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
            answer.question.text_content.get('th', ''),
            answer.question.text_content.get('en', ''),
            answer.question.get_question_type_display(), # 'คะแนน 1-5 ดาว'
            answer.answer_value
        ])

    return response


def export_responses_excel(request):
    """ส่งออกข้อมูลเป็น Excel (.xlsx)"""
    queryset = get_filtered_data_for_export(request)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Responses"

    # 1. เขียนหัวตาราง (Header)
    headers = [
        'Response ID', 'Service Point', 'Submitted At',
        'Question (TH)', 'Question (EN)', 'Question Type', 'Answer Value'
    ]
    ws.append(headers)

    # (Optional) จัดสไตล์หัวตาราง...
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = openpyxl.styles.Font(bold=True)
        column_letter = get_column_letter(col_num)
        if col_num in [4, 5]:
            ws.column_dimensions[column_letter].width = 40
        else:
            ws.column_dimensions[column_letter].width = 20

    for answer in queryset:
        local_submitted_at = timezone.localtime(answer.response.submitted_at)       
        # 2b. ทำให้เป็น Naive (ลบ tzinfo) เพื่อให้ openpyxl รับได้
        naive_submitted_at = local_submitted_at.replace(tzinfo=None)
        ws.append([
            answer.response.id,
            answer.response.service_point.name,
            naive_submitted_at, # <-- ใช้ตัวแปรที่แปลงแล้ว
            answer.question.text_content.get('th', ''),
            answer.question.text_content.get('en', ''),
            answer.question.get_question_type_display(),
            answer.answer_value
        ])
    # 3. สร้าง Response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="survey_responses.xlsx"'},
    )
    wb.save(response)
    return response

class SuperuserRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

# 1. หน้า "รายการ" คำถาม
class QuestionListView(SuperuserRequiredMixin, TemplateView):
    template_name = 'survey/question_list.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)    
        # (ดึงข้อมูลสำหรับ 3 แท็บ)
        if self.request.user.is_superuser:
            # (แก้ 'select_related' และ 'order_by' ไม่ให้มี 'section')
            context['all_questions'] = Question.objects.all().select_related('survey_version').order_by('survey_version', 'order')
            context['all_versions'] = SurveyVersion.objects.all().select_related('survey').order_by('survey', 'status')
            context['all_surveys'] = Survey.objects.all().order_by('title_th')
        else:
            # (สำหรับ Manager ในอนาคต)
            context['all_questions'] = Question.objects.filter(created_by_user=self.request.user).select_related('survey_version').order_by('survey_version', 'order')
            context['all_versions'] = SurveyVersion.objects.filter(created_by_user=self.request.user).select_related('survey').order_by('survey', 'status')
            context['all_surveys'] = Survey.objects.filter(created_by_user=self.request.user).order_by('title_th')      
        return context

# --- (2. แก้ไข QuestionCreateView/UpdateView) ---
# (ตรวจสอบว่า 'success_url' ถูกต้อง)
class QuestionCreateView(SuperuserRequiredMixin, CreateView):
    model = Question
    form_class = QuestionForm
    template_name = 'survey/question_form.html'
    success_url = reverse_lazy('survey:survey_management') # (แก้เป็น 'survey_management')
    
    def form_valid(self, form):
        form.save(user=self.request.user)
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'เพิ่มคำถามใหม่'
        context['cancel_url'] = reverse_lazy('survey:survey_management') # (แก้เป็น 'survey_management')
        return context

class QuestionUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'survey/question_form.html'
    success_url = reverse_lazy('survey:survey_management') # (แก้เป็น 'survey_management')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'แก้ไขคำถาม'
        context['cancel_url'] = reverse_lazy('survey:survey_management') # (แก้เป็น 'survey_management')
        return context

# Mixin (สำหรับ Superuser)
class SuperuserRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
    
# 6. CRUD สำหรับ SurveyVersion
@login_required
@user_passes_test(is_superuser)
def survey_version_list_view(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id)
    versions = survey.versions.all().order_by('-created_at')
    return render(request, 'survey/version_list.html', {
        'survey': survey,
        'versions': versions
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def version_create_view(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id)
    
    if request.method == 'POST':
        form = SurveyVersionForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic(): # ใช้ Transaction เพื่อความปลอดภัย
                    # 1. สร้าง Version (ยังไม่ save ลง DB)
                    version = form.save(commit=False)
                    version.survey = survey 
                    if hasattr(version, 'created_by_user'):
                        version.created_by_user = request.user
                    # 2. บันทึก Version ลง DB
                    version.save()
                    # 3. บันทึกจุดบริการ (Service Points) ลงตารางกลาง
                    # ดึงข้อมูลที่เลือกจากฟอร์ม
                    selected_points = form.cleaned_data.get('service_points')
                    if selected_points:
                        SurveyServicePoint.objects.filter(survey_version=version).delete()
                        new_relations = []
                        for sp in selected_points:
                            new_relations.append(
                                SurveyServicePoint(survey_version=version, service_point=sp)
                            )
                        # บันทึกทีเดียว (Bulk Create)
                        SurveyServicePoint.objects.bulk_create(new_relations)

                messages.success(request, f'สร้างเวอร์ชัน {version.version_number} และบันทึกจุดบริการเรียบร้อย!')
                return redirect('survey:question_list', version_id=version.id)
            
            except Exception as e:
                messages.error(request, f"เกิดข้อผิดพลาดในการบันทึก: {e}")
    else:
        last_ver = survey.versions.order_by('-created_at').first()
        next_num = "1.0"
        
        if last_ver:
            try:
                val = float(last_ver.version_number)
                next_num = str(round(val + 1.0, 1))
            except ValueError:
                next_num = f"{last_ver.version_number}.1"
        form = SurveyVersionForm(initial={'version_number': next_num})

    return render(request, 'survey/generic_form.html', {
        'form': form,
        'page_title': f'สร้างเวอร์ชันใหม่ ({survey.title_th})',
        'btn_text': 'สร้างและไปเพิ่มคำถาม',
        'cancel_url': reverse('survey:survey_version_list', args=[survey.id])
    })

@login_required
@user_passes_test(is_superuser)
def version_edit_view(request, pk):
    # 1. ดึงเวอร์ชันที่จะแก้ไข
    version = get_object_or_404(SurveyVersion, pk=pk)
    if request.method == 'POST':
        # 2. บันทึกทับข้อมูลเดิม
        form = SurveyVersionForm(request.POST, instance=version)
        if form.is_valid():
            try:
                with transaction.atomic():
                    edited_version = form.save(commit=False)
                    if hasattr(edited_version, 'created_by_user'):
                         # (กันไม่ให้ user ที่แก้กลายเป็นคนสร้าง)
                        pass 
                    edited_version.save()
                    selected_points = form.cleaned_data.get('service_points')
                    SurveyServicePoint.objects.filter(survey_version=edited_version).delete()
                    # สร้างของใหม่
                    if selected_points:
                        new_relations = []
                        for sp in selected_points:
                            new_relations.append(
                                SurveyServicePoint(survey_version=edited_version, service_point=sp)
                            )
                        SurveyServicePoint.objects.bulk_create(new_relations)

                messages.success(request, f'แก้ไขเวอร์ชัน {edited_version.version_number} เรียบร้อย')

                return redirect('survey:survey_version_list', survey_id=version.survey.id)
            except Exception as e:
                messages.error(request, f"เกิดข้อผิดพลาด: {e}")
    else:
        form = SurveyVersionForm(instance=version)

    return render(request, 'survey/generic_form.html', {
        'form': form,
        'page_title': f'แก้ไขเวอร์ชัน: {version.version_number}',
        'btn_text': 'บันทึกการแก้ไข',
        'cancel_url': reverse('survey:survey_version_list', args=[version.survey.id])
    })



@login_required
@user_passes_test(is_superuser)
def survey_create_flow_view(request):
    if request.method == 'POST':
        survey_form = SurveyForm(request.POST)
        version_form = SurveyVersionForm(request.POST)
        
        if survey_form.is_valid() and version_form.is_valid():
            try:
                with transaction.atomic():
                    # 1. บันทึก Survey
                    survey = survey_form.save(commit=False)
                    survey.created_by_user = request.user
                    survey.save()
                    # 2. บันทึก Version
                    version = version_form.save(commit=False)
                    version.survey = survey
                    version.created_by_user = request.user
                    version.save()
                    # 3. (จุดที่แก้) บันทึกจุดบริการลงตารางกลาง (SurveyServicePoint)
                    # ดึงข้อมูลที่เลือกมาจากฟอร์มโดยตรง
                    selected_points = version_form.cleaned_data.get('service_points')
            
                    if selected_points:
                        new_relations = []
                        for sp in selected_points:
                            new_relations.append(
                                SurveyServicePoint(survey_version=version, service_point=sp)
                            )
                        SurveyServicePoint.objects.bulk_create(new_relations)
        
                messages.success(request, f'สร้างแบบสอบถาม "{survey.title_th}" เรียบร้อยแล้ว')
                return redirect('survey:question_list', version_id=version.id)
                
            except Exception as e:
                messages.error(request, f"เกิดข้อผิดพลาด: {e}")
    else:
        survey_form = SurveyForm()
        version_form = SurveyVersionForm(initial={'version_number': '1.0'})

    return render(request, 'survey/management/survey_create_flow.html', {
        'survey_form': survey_form,
        'version_form': version_form,
        'title': 'สร้างแบบสอบถามใหม่'
    })

# --- 2. แสดงรายการคำถาม (Question List) ---
@login_required
@user_passes_test(is_superuser)
def question_list_view(request, version_id):
    version = get_object_or_404(SurveyVersion, pk=version_id)
    questions = version.questions.all().order_by('order')
    
    return render(request, 'survey/question_list.html', {
        'version': version,
        'survey': version.survey,
        'questions': questions
    })

# --- 3. เพิ่มคำถาม (Question Create) ---
@login_required
@user_passes_test(is_superuser)
def question_create_view(request, version_id):
    version = get_object_or_404(SurveyVersion, pk=version_id)
    
    if request.method == 'POST':
        form = QuestionForm(request.POST) 
        if form.is_valid():
            question = form.save(commit=False)
            question.survey_version = version  
            
            if hasattr(question, 'created_by_user'):
                question.created_by_user = request.user
            
            question.save()
            messages.success(request, 'เพิ่มคำถามสำเร็จ')
            return redirect('survey:question_list', version_id=version.id)
    else:
        last_order = version.questions.count() + 1
        form = QuestionForm(initial={'order': last_order})

    return render(request, 'survey/generic_form.html', {
        'form': form, 
        'version': version,
        'page_title': f'เพิ่มคำถาม (v{version.version_number})',
        'btn_text': 'บันทึกคำถาม',
        'cancel_url': reverse('survey:question_list', args=[version.id])
    })

# 7. CRUD สำหรับ Survey
class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

# 1. หน้าแสดงรายการ (List)
class SurveyListView(SuperuserRequiredMixin, ListView):
    model = Survey
    template_name = 'survey/survey_list.html'
    context_object_name = 'surveys'
    ordering = ['-created_at']

    def get_queryset(self):
        from django.db.models import Count
        return Survey.objects.annotate(version_count=Count('versions')).order_by('-created_at')

# 2. หน้าสร้าง (Create)
class SurveyCreateView(SuperuserRequiredMixin, CreateView):
    model = Survey
    form_class = SurveyForm
    template_name = 'survey/survey_form.html'
    success_url = reverse_lazy('survey:survey_list')

    def form_valid(self, form):
        messages.success(self.request, "สร้างแบบสอบถามเรียบร้อยแล้ว")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "สร้างแบบสอบถามใหม่"
        context['btn_text'] = "ยืนยันการสร้าง"
        return context

# 3. หน้าแก้ไข (Update)
class SurveyUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Survey
    form_class = SurveyForm
    template_name = 'survey/survey_form.html'
    success_url = reverse_lazy('survey:survey_list')

    def form_valid(self, form):
        messages.success(self.request, "แก้ไขข้อมูลเรียบร้อยแล้ว")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"แก้ไข: {self.object.title_th}"
        context['btn_text'] = "บันทึกการแก้ไข"
        return context

# 4. หน้าลบ (Delete) - (เผื่อไว้ใช้)
class SurveyDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Survey
    template_name = 'survey/survey_confirm_delete.html'
    success_url = reverse_lazy('survey:survey_list')
    
class QuestionDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Question
    template_name = 'survey/generic_delete_confirm.html'
    success_url = reverse_lazy('survey:survey_management')