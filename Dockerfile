FROM odoo:18.0

USER root

# إنشاء مجلد للموديول المخصص ونسخ الملفات إليه
RUN mkdir -p /mnt/extra-addons/dawaee_platform
COPY . /mnt/extra-addons/dawaee_platform

# ضبط الصلاحيات للمستخدم odoo
RUN chown -R odoo:odoo /mnt/extra-addons/dawaee_platform

USER odoo

# أمر التشغيل مع ربط المنفذ الذي يحدده Render تلقائياً
CMD ["sh", "-c", "odoo --http-port=${PORT:-8069} --db_host=${HOST} --db_port=${DB_PORT:-5432} --db_user=${USER} --db_password=${PASSWORD} -d dawee_db"]
