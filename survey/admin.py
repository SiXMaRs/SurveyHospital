# ใน survey/admin.py
from django.contrib import admin
from .models import ServicePoint # <-- Import

# ... (อาจจะมีโมเดลอื่น)

# ทำให้ ServicePoint ไปโผล่ในหน้า Admin
@admin.register(ServicePoint)
class ServicePointAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code')
    search_fields = ('name', 'code')