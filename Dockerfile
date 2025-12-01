# ใช้ Python 3.11
FROM python:3.11-slim

# ตั้งค่า Environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# ตั้งค่า Working Directory
WORKDIR /app

# --- ส่วนที่แก้ไข ---
# ติดตั้ง System dependencies สำหรับ MySQL Client (และ pkg-config ที่ขาดหายไป)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
# ------------------

# Copy requirements.txt และติดตั้ง Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy โค้ดทั้งหมดเข้าสู่ container
COPY . .

# เปิด Port 8000
EXPOSE 8000

# คำสั่งเริ่มต้น
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]