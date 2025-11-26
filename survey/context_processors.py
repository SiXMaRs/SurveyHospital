from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        # ดึงแจ้งเตือนที่ยังไม่อ่าน
        notifs = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')
        return {
            'unread_notifications_count': notifs.count(),
            'notifications_list': notifs[:5] # ส่งไปแสดงผลแค่ 5 อันล่าสุด
        }
    return {}