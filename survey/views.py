from django.shortcuts import render, get_object_or_404, redirect
from rest_framework import generics, permissions
from .serializers import ManagerCreateSerializer, USerDetailSerializer, ServicePointSerializer
from .models import *
from django.utils import timezone 
import json
from django.db.models import Count, Avg, Q, F
from django.db.models.functions import Cast , TruncDay
from django.db.models import IntegerField
from datetime import timedelta , datetime
from django.contrib.auth.decorators import login_required 
from django.contrib.auth.models import User, Group 
from django.contrib.auth.decorators import login_required
import openpyxl
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
import csv

class ManagerCreateView(generics.CreateAPIView):
    serializer_class = ManagerCreateSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

class UserMeView(generics.RetrieveAPIView):
    serializer_class = USerDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class ServicePointListView(generics.ListAPIView):
    """
    API endpoint สำหรับดึงรายชื่อจุดให้บริการ (ServicePoint) ทั้งหมด
    """
    queryset = ServicePoint.objects.all() # ดึงข้อมูล ServicePoint ทั้งหมด
    serializer_class = ServicePointSerializer
    
    # กำหนดสิทธิ์: ต้อง Login ก่อนถึงจะดูได้
    permission_classes = [permissions.IsAuthenticated]

@login_required
def index(request):
    return render(request, "index.html")

def survey_display_view(request, service_point_id):
    """
    View สำหรับ "แสดงผล" แบบสอบถามที่ Kiosk หรือ QR
    โดยค้นหาจาก ServicePoint ID
    """
    
    # 1. ค้นหา ServicePoint นี้ (ถ้าไม่เจอ จะ 404)
    service_point = get_object_or_404(ServicePoint, id=service_point_id)
    lang = request.GET.get('lang', 'th')    
    
    # 2. ค้นหา "เวอร์ชัน" ที่ "ACTIVE" และ "ผูก" อยู่กับ ServicePoint นี้
    #    (เลือกอันที่เผยแพร่ล่าสุด)
    active_version = SurveyVersion.objects.filter(
        service_points=service_point, 
        status='ACTIVE'
    ).order_by('-published_at').first() # .first() เพื่อเอาอันเดียว

    # 3. ส่งข้อมูลไปที่ Template
    context = {
        'service_point': service_point,
        'survey_version': active_version, # จะเป็น None ถ้าไม่เจอ
        'lang': lang
    }
    
    return render(request, 'survey/display.html', context)

def survey_submit_view(request, version_id):
    if request.method != 'POST':
        return redirect('/') 

    survey_version = get_object_or_404(SurveyVersion, id=version_id)
    
    # --- ดึง service_point_id จากฟอร์มที่ซ่อนไว้ ---
    service_point_pk = request.POST.get('service_point_id')

    new_response = Response.objects.create(
        survey_version=survey_version,
        service_point_id=service_point_pk, # <-- ใช้ ID ที่ดึงมา
        submitted_at=timezone.now(),
    )
    
    # ... (โค้ดบันทึก ResponseAnswer (วนลูป) ... )
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
                pass # ข้ามถ้ามี Error

    # --- ส่วนที่แก้ไข ---
    # ส่ง service_point_pk (เช่น 49) ไปให้หน้า "ขอบคุณ"
    context = {
        'service_point_pk': service_point_pk
    }
    return render(request, 'survey/thankyou.html', context)



# GIST: file:/survey/views.py (ฟังก์ชัน dashboard_view)

# GIST: file:/survey/views.py


@login_required 
def dashboard_view(request):
    """
    View สำหรับหน้า Dashboard (Layout 6-Card Grid)
    (แก้ไข NameError และ ValueError เรื่อง Timezone)
    """

    # --- A. ตรรกะการกรอง (Filters) ---
    
    # A1: กรองตาม Manager (สิทธิ์ผู้ใช้)
    user = request.user
    base_service_points = ServicePoint.objects.all()
    managers_list = User.objects.none() 
    
    if user.is_authenticated:
        if not user.is_superuser:
            base_service_points = user.managed_points.all()
            # --- แก้ไขบรรทัดนี้ ---
            managers_list = User.objects.filter(id=user.id).prefetch_related('managed_points')
        else:
            try:
                managers_group = Group.objects.get(name='Managers')
                # --- แก้ไขบรรทัดนี้ ---
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
    # (ตัวแปรนี้คือตัวแปรที่ถูกต้อง)
    filtered_responses_for_charts_and_ticker = Response.objects.filter(
        service_point__in=base_service_points, 
        submitted_at__gte=start_date,       
        submitted_at__lt=end_date_for_query 
    )

    # --- C. คำนวณข้อมูล (สำหรับ 6 การ์ด) ---

    # Card 1: KPIs (ซ้ายบน)
    total_active_questions = Question.objects.filter(
        section__survey_version__status='ACTIVE'
    ).distinct().count()
    
    # (เราจะคำนวณ total_responses ทีหลัง)

    # Card 2: Service Point List (ขวาบน)
    # (ใช้ข้อมูลรวม ไม่กรองตามวัน)
    all_service_points_with_counts = base_service_points.annotate(
        response_count=Count('response', filter=Q(response__service_point__in=base_service_points))
    ).order_by('-response_count')

    
    # Card 3: กราฟแท่งรายสัปดาห์ (ซ้ายกลาง) - ใช้ข้อมูลที่กรองตามวัน
    date_labels = []
    day_counts_dict = {}
    current_date = start_date
    while current_date <= end_date:
        date_labels.append(current_date.strftime('%a')) 
        day_counts_dict[current_date] = 0
        current_date += timedelta(days=1)

    # --- (นี่คือส่วนที่แก้ไข) ---
    # 1. ลบบล็อกโค้ด 'filtered_responses_for_bar = ...' ที่มีปัญหาทิ้งไป
    
    # 2. แก้ไขบรรทัดนี้: 
    #    เปลี่ยนจาก filtered_responses_for_bar 
    #    เป็น filtered_responses_for_charts_and_ticker
    response_times = filtered_responses_for_charts_and_ticker.values_list('submitted_at', flat=True)
    # --- (จบส่วนที่แก้ไข) ---

    # 3. วนลูปและแปลงเป็นเวลาท้องถิ่น (Asia/Bangkok) ใน Python
    for submitted_at_utc in response_times:
        local_time = timezone.localtime(submitted_at_utc)
        date_only = local_time.date() 
        if date_only in day_counts_dict:
            day_counts_dict[date_only] += 1
    
    bar_data_weekly = [day_counts_dict[day] for day in sorted(day_counts_dict.keys())]
    
    # KPI Total Responses (คำนวณจากข้อมูลที่กรองแล้ว)
    total_responses = filtered_responses_for_charts_and_ticker.count()


    # Card 4: Pie Chart (ขวากลาง)
    pie_data_all = base_service_points.annotate(
        response_count=Count('response', filter=Q(response__in=filtered_responses_for_charts_and_ticker))
    ).filter(response_count__gt=0).order_by('-response_count')
    
    pie_labels = [sp.name for sp in pie_data_all]
    pie_data = [sp.response_count for sp in pie_data_all]
    
    # Card 5: Admin List (ซ้ายล่าง)
    # (managers_list ถูกเตรียมไว้แล้วใน A1)
    
    # Card 6: Ticker (ขวาล่าง)
    recent_feedback = ResponseAnswer.objects.filter(
        response__in=filtered_responses_for_charts_and_ticker, 
        question__question_type='TEXTAREA'
    ).exclude(answer_value__exact='').select_related(
        'response__service_point'
    ).order_by('-response__submitted_at')[:5]

    # --- D. ส่งข้อมูลทั้งหมดไปที่ Template ---
    context = {
        # Card 1 KPIs
        'total_responses': total_responses,
        'total_service_points_in_view': base_service_points.count(),
        'total_active_questions': total_active_questions,

        # Card 2 Service Point List
        'all_service_points_with_counts': all_service_points_with_counts,

        # Card 3 Bar Chart
        'bar_labels_weekly': json.dumps(date_labels),
        'bar_data_weekly': json.dumps(bar_data_weekly),
        
        # Card 4 Pie Chart
        'pie_labels': json.dumps(pie_labels),
        'pie_data': json.dumps(pie_data),

        # Card 5 Admin List
        'managers_list': managers_list,
        
        # Card 6 Ticker
        'recent_feedback': recent_feedback,

        # Filter values
        'start_date': start_date_str,
        'end_date': end_date_str,
    }

    return render(request, 'survey/dashboard.html', context)



def get_filtered_data_for_export(request):
    """
    (ฟังก์ชันช่วย) ดึงข้อมูลดิบ (Raw Data) ตาม Filter
    เพื่อใช้ร่วมกันทั้ง CSV และ Excel
    """
    
    # --- 1. ตรรกะการกรอง (Filters) ---
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
        'response',                 # JOIN ตาราง Response
        'response__service_point',  # JOIN ตาราง ServicePoint
        'question'                  # JOIN ตาราง Question
    ).order_by('response__submitted_at') # เรียงตามเวลา

    return queryset


def export_responses_csv(request):
    """
    ส่งออกข้อมูลเป็น CSV
    """
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="survey_responses.csv"'},
    )
    response.write('\ufeff') # BOM สำหรับให้ Excel อ่าน UTF-8 (ภาษาไทย)

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
    """
    ส่งออกข้อมูลเป็น Excel (.xlsx)
    """
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

    # --- 2. เขียนข้อมูล (Data) (นี่คือส่วนที่แก้ไข) ---
    for answer in queryset:
        
        # 2a. แปลงเวลา (Aware UTC) ให้เป็น Local Time (Aware)
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