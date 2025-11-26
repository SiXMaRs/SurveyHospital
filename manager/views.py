from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sessions.models import Session
from django.views.generic import UpdateView, DeleteView
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.contrib import messages
from datetime import datetime, timedelta
from django.urls import reverse
from django.db.models import Count, Q, Avg, F
from survey.models import *
from .forms import * 
import json

@login_required
def dashboard_view(request):
    user = request.user
    base_service_points = user.managed_points.all()
    # Manager List: แสดงแค่ตัว Manager เองคนเดียว (เพื่อให้ Template ไม่ต้องแก้เยอะ)
    managers_list = User.objects.filter(
        managed_points__in=base_service_points
    ).distinct().prefetch_related('managed_points') 
    
    today = timezone.now().date()
    # Default: สัปดาห์ปัจจุบัน (จันทร์ - อาทิตย์)
    start_date_default = today - timedelta(days=today.weekday()) 
    end_date_default = start_date_default + timedelta(days=6) 
    end_date_str = request.GET.get('end_date', end_date_default.strftime('%Y-%m-%d'))
    start_date_str = request.GET.get('start_date', start_date_default.strftime('%Y-%m-%d'))
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        start_date = start_date_default
        end_date = end_date_default
        
    # บวก 1 วันเพื่อให้ครอบคลุมเวลา 23:59:59 ของวันสิ้นสุด
    end_date_for_query = end_date + timedelta(days=1)
    
    # --- 3. สร้าง Queryset หลัก (Main Filter) ---
    # กรอง Response ทั้งหมด โดยต้องมาจากจุดบริการของเรา (base_service_points) และอยู่ในช่วงเวลา
    filtered_responses = Response.objects.filter(
        service_point__in=base_service_points, 
        submitted_at__gte=start_date, 
        submitted_at__lt=end_date_for_query 
    )

    # --- 4. คำนวณข้อมูล (KPIs) ---
    # จำนวนคำถามที่ Active (เท่ากันทุกคน)
    total_active_questions = Question.objects.filter(
        survey__status=Survey.Status.ACTIVE
    ).count()
    
    # ยอดรวมการตอบ (เฉพาะของ Manager คนนี้)
    total_responses = filtered_responses.count()
    total_service_points_in_view = base_service_points.count()
    total_managers = managers_list.count()

    # --- 5. List: รายการจุดบริการพร้อมยอด (Service Point List) ---
    all_service_points_with_counts = base_service_points.annotate(
        response_count=Count('response', filter=Q(response__in=filtered_responses))
    ).order_by('-response_count')

    # --- 6. Chart: กราฟแท่ง (Bar Chart) ---
    date_labels = []
    day_counts_dict = {}
    current_date = start_date
    
    # สร้างแกน X ให้ครบทุกวันในช่วงที่เลือก
    while current_date <= end_date:
        date_labels.append(current_date.strftime('%a %d/%m')) 
        day_counts_dict[current_date] = 0
        current_date += timedelta(days=1)

    # เติมข้อมูลลงในวันที่มีการตอบ
    response_times = filtered_responses.values_list('submitted_at', flat=True)
    for submitted_at_utc in response_times:
        local_time = timezone.localtime(submitted_at_utc)
        date_only = local_time.date() 
        if date_only in day_counts_dict:
            day_counts_dict[date_only] += 1
            
    bar_data_weekly = [day_counts_dict[day] for day in sorted(day_counts_dict.keys())]

    # --- 7. Chart: กราฟวงกลม (Pie Chart) ---
    pie_data_query = all_service_points_with_counts.filter(response_count__gt=0)
    pie_labels = [sp.name for sp in pie_data_query]
    pie_data = [sp.response_count for sp in pie_data_query]

    # --- 8. ข้อเสนอแนะ (Feedback Ticker) ---
    recent_feedback = ResponseAnswer.objects.filter(
        response__in=filtered_responses, # กรองแล้ว
        question__question_type='TEXTAREA'
    ).exclude(
        Q(answer_text__isnull=True) | Q(answer_text__exact='')
    ).select_related(
        'response__service_point'
    ).order_by('-response__submitted_at')[:5]
    
    # --- 9. ส่ง Context ไป Template ---
    context = {
        'total_responses': total_responses,
        'total_managers': total_managers,
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

    return render(request, 'manager/dashboard.html', context)

@login_required
def manager_list_view(request):
    user = request.user
    
    # 1. หาจุดบริการและเพื่อนร่วมงาน (co_managers)
    my_points = user.managed_points.all()
    co_managers = User.objects.filter(
        managed_points__in=my_points,
        is_superuser=False
    ).distinct().prefetch_related('managed_points').order_by('username')

    # 2. Search Logic (ถ้ามี)
    query = request.GET.get('q', '')
    if query:
        co_managers = co_managers.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )

    # 3. Online Status Logic (หา Session ทั้งหมดที่ Active)
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    all_online_user_ids = set()
    for session in sessions:
        data = session.get_decoded()
        uid = data.get('_auth_user_id')
        if uid:
            all_online_user_ids.add(int(uid))

    co_manager_ids = set(co_managers.values_list('id', flat=True))
    
    # หาจุดตัด (คนที่ออนไลน์ AND เป็นเพื่อนร่วมงานเรา)
    online_co_managers_count = len(co_manager_ids.intersection(all_online_user_ids))

    context = {
        'page_title': 'ผู้ดูแลจุดบริการ (ทีมงาน)',
        'managers': co_managers,
        'search_query': query,
        'online_user_ids': all_online_user_ids, # ส่งไปใช้ใน loop ตารางเหมือนเดิม
        'online_count': online_co_managers_count, # 🔴 ส่งตัวเลขที่ถูกต้องไปแสดงในการ์ด
        'my_points': my_points,
    }
    
    return render(request, 'manager/manager_list.html', context)

@login_required
def survey_list_view(request):
    user = request.user
    my_points = user.managed_points.all()

    surveys = Survey.objects.filter(
        service_point__in=my_points
    ).select_related('service_point', 'service_point__group').annotate(
        question_count=Count('questions') 
    ).order_by('-created_at')

    # --- 📊 ส่วนที่ 1: คำนวณ Stats สำหรับการ์ด (คำนวณจากทั้งหมดก่อนกรอง) ---
    total_surveys = surveys.count()
    total_questions = Question.objects.filter(survey__in=surveys).count()
    total_service_points = my_points.count()

    # --- 🔍 ส่วนที่ 2: Logic การกรอง (Filter Bar) ---
    search_query = request.GET.get('q')
    group_filter = request.GET.get('group')
    point_filter = request.GET.get('point')

    if search_query:
        surveys = surveys.filter(
            Q(title_th__icontains=search_query) | 
            Q(title_en__icontains=search_query)
        )
    
    if group_filter:
        surveys = surveys.filter(service_point__group_id=group_filter)
    
    if point_filter:
        surveys = surveys.filter(service_point_id=point_filter)

    # เตรียมข้อมูลใส่ Dropdown ใน Filter Bar (เฉพาะที่เกี่ยวข้องกับ Manager)
    filter_groups = ServiceGroup.objects.filter(service_points__in=my_points).distinct()
    filter_points = my_points

    # --- 📝 ส่วนที่ 3: Handle Form (Create New) ---
    show_modal = False 

    if request.method == 'POST':
        form = ManagerSurveyForm(user, request.POST)
        if form.is_valid():
            new_status = form.cleaned_data.get('status')
            new_service_point = form.cleaned_data.get('service_point')

            # === CONSTRAINT CHECK (1 Active per Point) ===
            if new_status == 'ACTIVE':
                if Survey.objects.filter(
                    service_point=new_service_point,
                    status='ACTIVE'
                ).exists():
                    messages.error(request, f"ไม่สามารถเปิดใช้งานได้: จุดบริการ **'{new_service_point.name}'** มีแบบสอบถามที่เปิดใช้งานอยู่แล้ว")
                    show_modal = True
                    
                    # ส่ง Context กลับไปเพื่อให้หน้าเว็บไม่พังและ Modal เปิดค้างไว้
                    context = {
                        'page_title': 'จัดการแบบสอบถาม',
                        'surveys': surveys,
                        'form': form,
                        'show_modal': show_modal,
                        # ต้องส่งค่าพวกนี้กลับไปด้วย ไม่งั้นหน้าจอจะ error หรือการ์ดหาย
                        'total_surveys': total_surveys,
                        'total_questions': total_questions,
                        'total_service_points': total_service_points,
                        'groups': filter_groups,
                        'service_points': filter_points,
                    }
                    return render(request, 'manager/survey_list.html', context)

            # ถ้าผ่านเงื่อนไข -> บันทึก
            survey = form.save(commit=False)
            survey.version_number = "1.0"
            survey.save()
            messages.success(request, "สร้างแบบสอบถามเรียบร้อยแล้ว")
            return redirect('manager:survey_list')
        else:
            show_modal = True
            messages.error(request, "เกิดข้อผิดพลาด กรุณาตรวจสอบข้อมูล")
    else:
        form = ManagerSurveyForm(user)

    # --- 📦 ส่วนที่ 4: Context Final ---
    context = {
        'page_title': 'จัดการแบบสอบถาม',
        'surveys': surveys,
        'form': form,
        'show_modal': show_modal,
        
        # Stats Cards Variables
        'total_surveys': total_surveys,
        'total_questions': total_questions,
        'total_service_points': total_service_points,
        
        # Dropdown Choices
        'groups': filter_groups,
        'service_points': filter_points,
    }
    return render(request, 'manager/survey_list.html', context)
    
@login_required
def survey_edit_view(request, pk):
    # ต้องดึง survey เดิมมาก่อน
    original_survey = get_object_or_404(Survey, pk=pk, service_point__in=request.user.managed_points.all())

    if request.method == 'POST':
        # 🔴 ใช้ original_survey เป็น instance ใน form
        form = ManagerSurveyForm(request.user, request.POST, instance=original_survey)
        
        if form.is_valid():
            changed_data = form.changed_data
            new_status = form.cleaned_data.get('status')
            new_service_point = form.cleaned_data.get('service_point') # ดึง Service Point ใหม่

            # --- 🔴 STEP 1: CONSTRAINT CHECK (1 ACTIVE SURVEY PER SERVICE POINT) ---
            if new_status == 'ACTIVE':
                # ตรวจสอบว่ามีแบบสอบถามอื่น (ที่ไม่ใช่ตัวปัจจุบัน) ที่ Active อยู่แล้วหรือไม่
                if Survey.objects.filter(
                    service_point=new_service_point,
                    status='ACTIVE'
                ).exclude(pk=original_survey.pk).exists():
                    
                    messages.error(request, f"ไม่สามารถเปิดใช้งานได้: จุดบริการ **'{new_service_point.name}'** มีแบบสอบถามที่เปิดใช้งานอยู่แล้ว")
                    return redirect('manager:survey_list')

            # --- STEP 2: APPLY SAVE LOGIC (Versioning) ---
            
            # CASE A: Change only Status -> Update In-place (ไม่ต้องสร้างเวอร์ชันใหม่)
            if len(changed_data) == 1 and 'status' in changed_data:
                # ถ้าเปลี่ยนสถานะอย่างเดียว (และผ่าน Constraint Check แล้ว)
                form.save()
                messages.success(request, "อัปเดตสถานะเรียบร้อยแล้ว (ไม่สร้างเวอร์ชันใหม่)")
            else:
                try:
                    with transaction.atomic():
                        
                        # 2.1 [Cleanup] ถ้าเวอร์ชันใหม่เป็น ACTIVE, ควรกำหนดให้เวอร์ชันเดิมเป็น DRAFT
                        if new_status == 'ACTIVE':
                             Survey.objects.filter(pk=original_survey.pk).update(status='DRAFT')

                        # 2.2 สร้าง Survey Object ใหม่
                        new_survey = form.save(commit=False)
                        new_survey.pk = None # สำคัญ: ลบ PK เพื่อให้ Django สร้าง record ใหม่
                        
                        # Version logic: เพิ่มเลขเวอร์ชัน
                        try:
                            current_ver = float(original_survey.version_number or 0)
                        except ValueError:
                            current_ver = 0 # กรณีที่ format ผิด
                            
                        new_survey.version_number = f"{int(current_ver) + 1}.0"
                        
                        new_survey.save()

                        # 2.3 Clone Questions (คัดลอกคำถามจากเวอร์ชันเดิม)
                        old_questions = original_survey.questions.all().order_by('order')
                        new_questions = [
                            Question(
                                survey=new_survey,
                                # **ใส่ฟิลด์คำถามทั้งหมดที่ต้องการโคลนมาที่นี่**
                                text_th=q.text_th,
                                text_en=q.text_en,
                                question_type=q.question_type,
                                order=q.order,
                                is_required=q.is_required
                                # ... เพิ่มฟิลด์อื่น ๆ เช่น choices, min_value, max_value ตาม Model ...
                            ) for q in old_questions
                        ]
                        Question.objects.bulk_create(new_questions)

                    messages.success(request, f"บันทึกเวอร์ชันใหม่ (v{new_survey.version_number}) เรียบร้อยแล้ว")

                except Exception as e:
                    messages.error(request, f"เกิดข้อผิดพลาดในการสร้างเวอร์ชัน: {e}")
            
            return redirect('manager:survey_list')
        else:
            messages.error(request, "เกิดข้อผิดพลาด กรุณาตรวจสอบข้อมูล")

    return redirect('manager:survey_list')

# (แถม) ฟังก์ชันลบ (ถ้ายังไม่มี)
@login_required
def survey_delete_view(request, pk):
    survey = get_object_or_404(Survey, pk=pk, service_point__in=request.user.managed_points.all())
    
    if request.method == 'POST':
        survey.delete()
        messages.success(request, "ลบแบบสอบถามเรียบร้อยแล้ว")
        return redirect('manager:survey_list')

    return redirect('manager:survey_list')


@login_required
def question_list_view(request, survey_id):
    survey = get_object_or_404(Survey, pk=survey_id, service_point__in=request.user.managed_points.all())
    questions = survey.questions.all().order_by('order')
    show_modal = False

    if request.method == 'POST':
        form = ManagerQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.survey = survey
            question.save()
            messages.success(request, 'เพิ่มคำถามเรียบร้อยแล้ว')
            return redirect('manager:question_list', survey_id=survey.id)
        else:
            show_modal = True
            messages.error(request, "กรุณาตรวจสอบข้อมูล")
    else:
        # Auto Run Order: หาเลขลำดับถัดไป
        last_order = questions.count() + 1
        form = ManagerQuestionForm(initial={'order': last_order})

    context = {
        'survey': survey,
        'questions': questions,
        'form': form,
        'show_modal': show_modal,
        'page_title': f'จัดการคำถาม: {survey.title_th}'
    }

    return render(request, 'manager/question_list.html', context)

class QuestionUpdateView(LoginRequiredMixin, UpdateView):
    model = Question
    form_class = ManagerQuestionForm
    template_name = 'manager/question_form.html' 
    def get_queryset(self):
        return Question.objects.filter(
            survey__service_point__in=self.request.user.managed_points.all()
        )

    def get_success_url(self):
        messages.success(self.request, "แก้ไขคำถามเรียบร้อยแล้ว")
        return reverse('manager:question_list', args=[self.object.survey.id])

class QuestionDeleteView(LoginRequiredMixin, DeleteView):
    model = Question
    def get_queryset(self):
        # 🔒 Security Check
        return Question.objects.filter(
            survey__service_point__in=self.request.user.managed_points.all()
        )

    def get_success_url(self):
        messages.success(self.request, "ลบคำถามเรียบร้อยแล้ว")
        return reverse('manager:question_list', args=[self.object.survey.id])
 
    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

@login_required
def manager_assessment_results_view(request): # เปลี่ยนชื่อฟังก์ชันเพื่อแยกจาก Admin
    user = request.user
    manager_points = user.managed_points.all()

    group_id = request.GET.get('group_id')
    point_id = request.GET.get('point_id')
    score_filter = request.GET.get('score')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    responses = Response.objects.filter(
        service_point__in=manager_points 
    ).annotate(
        avg_score=Avg('answers__answer_rating')
    ).select_related('service_point', 'service_point__group').order_by('-submitted_at')

    if score_filter:
        try:
            min_score, max_score = map(int, score_filter.split('-'))
            if max_score == 5:
                responses = responses.filter(avg_score__gte=min_score, avg_score__lte=max_score)
            else:
                responses = responses.filter(avg_score__gte=min_score, avg_score__lt=max_score)
        except ValueError:
            pass

    if start_date_str and end_date_str:
        try:
            from datetime import datetime
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

    total_assessments = responses.count()
    total_suggestions = ResponseAnswer.objects.filter(
        response__in=responses,
        question__question_type='TEXTAREA'
    ).exclude(answer_text='').count()

    paginator = Paginator(responses, 10) 
    page_obj = paginator.get_page(request.GET.get('page'))

    # 5. Suggestions List (Logic นี้ใช้ได้เหมือนเดิม)
    recent_suggestions = ResponseAnswer.objects.filter(
        response__in=responses,
        question__question_type='TEXTAREA'
    ).exclude(answer_text='').select_related('response', 'response__service_point').order_by('-id')[:10]

    group_ids = manager_points.values_list('group_id', flat=True).distinct()
    groups = ServiceGroup.objects.filter(id__in=group_ids)
    points = manager_points # ใช้ managed_points ที่กรองไว้แล้ว
    
    # 🔴 ส่ง Map ที่กรองแล้วไปให้ JS
    point_map_json = json.dumps(_get_manager_point_map(manager_points))

    context = {
        'page_title': 'ผลการประเมิน',
        'total_assessments': total_assessments,
        'total_suggestions': total_suggestions,
        'page_obj': page_obj,
        'recent_suggestions': recent_suggestions,
        'groups': groups,
        'points': points,
        'point_map_json': point_map_json, # 👈 Map ที่กรองแล้ว
        'selected_group': int(group_id) if group_id else '',
        'selected_point': int(point_id) if point_id else '',
        'selected_score': score_filter,
        'start_date': start_date_str if start_date_str else '',
        'end_date': end_date_str if end_date_str else '',
    }
    return render(request, 'manager/assessment_results.html', context) # ใช้ Template เดิมได้

def _get_manager_point_map(manager_points_queryset):
    """สร้างแผนที่ (JSON) ของ {Group: [Points]} สำหรับ Manager"""
    point_map = {}
    groups = ServiceGroup.objects.filter(
        service_points__in=manager_points_queryset
    ).distinct().prefetch_related('service_points')
    
    for group in groups:
        manager_points_in_group = manager_points_queryset.filter(group=group).order_by('name')

        point_map[group.id] = [
            {'id': point.id, 'name': point.name}
            for point in manager_points_in_group
        ]
    return point_map

@login_required
def suggestion_list_view(request): # เปลี่ยนชื่อฟังก์ชัน
    user = request.user
    manager_points = user.managed_points.all()
    
    # 1. รับค่า Filter (เหมือนหน้า Assessment)
    group_id = request.GET.get('group_id')
    point_id = request.GET.get('point_id')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    search_query = request.GET.get('q', '')

    suggestions = ResponseAnswer.objects.filter(
        response__service_point__in=manager_points, # 👈 การกรองหลักสำหรับ Manager
        question__question_type='TEXTAREA'
    ).exclude(answer_text='').select_related(
        'response', 
        'response__service_point', 
        'response__service_point__group'
    ).order_by('-response__submitted_at')
    
    # 3. Apply Filters (เหมือนเดิม)
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

    paginator = Paginator(suggestions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    group_ids = manager_points.values_list('group_id', flat=True).distinct()
    groups = ServiceGroup.objects.filter(id__in=group_ids)
    
    points = manager_points # ใช้ managed_points ที่กรองไว้แล้ว
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
    return render(request, 'manager/suggestion_list.html', context)


