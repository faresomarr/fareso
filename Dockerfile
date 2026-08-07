# استخدام صورة أساسية تحتوي على نظام لينكس مدمج معه بيئة بايثون
FROM python:3.10-slim

# تثبيت Node.js و npm و git والأدوات الأساسية للنظام
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملفات المشروع بالكامل إلى الحاوية
COPY . .

# تثبيت مكتبات بايثون
RUN pip install --no-cache-dir python-telegram-bot requests

# تثبيت مكتبات Node.js مباشرة من المجلد الحالي (لأن الملفات كلها في الجذر)
RUN npm install

# تحديد الأمر الإفتراضي عند تشغيل الحاوية (تشغيل ملف بايثون الرئيسي)
CMD ["node", "index.js"]
