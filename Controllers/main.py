# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError


class DawaiWebsite(http.Controller):

    # 1. قائمة الأدوية العامة
    @http.route('/medicines', type='http', auth='public', website=True)
    def medicines_page(self, search='', **kwargs):
        domain = [('active', '=', True)]
        if search:
            domain += ['|', ('med_name', 'ilike', search), ('scientific_name', 'ilike', search)]
        medicines = request.env['dawai.medicine'].sudo().search(domain)
        return request.render('dawai_platform.patient_medicines_template', {
            'medicines': medicines,
            'search': search,
        })

    # 2. تفاصيل الدواء وعرض الصيدليات
    @http.route('/medicines/<int:medicine_id>', type='http', auth='public', website=True)
    def medicine_details(self, medicine_id, **kwargs):
        medicine = request.env['dawai.medicine'].sudo().browse(medicine_id)
        if not medicine.exists() or not medicine.active:
            return request.not_found()
        inventories = request.env['dawai.inventory'].sudo().search([
            ('med_id', '=', medicine.id),
            ('qty_net', '>', 0),
            ('active', '=', True)
        ])
        return request.render('dawai_platform.medicine_details_template', {
            'medicine': medicine,
            'inventories': inventories
        })

    # 3. مسار الحجز المطور (يستقبل GET لعرض الصفحة و POST لحفظ البيانات في الجدول 7)
    @http.route('/medicines/book/<int:inventory_id>', type='http', auth='user', methods=['GET', 'POST'], website=True)
    def book_medicine_action(self, inventory_id, **kwargs):
        inventory = request.env['dawai.inventory'].sudo().browse(inventory_id)
        if not inventory.exists() or not inventory.active:
            return request.not_found()

        current_user = request.env.user

        # البحث عن سجل المريض المرتبط بحساب المستخدم الحالي في نظام Odoo
        # (يفترض أن نموذج dawai.patient يحتوي على حقل user_id يربطه بحساب المستخدم)
        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', current_user.id)], limit=1)

        # إجراء حمائي: إذا لم يكن للمستخدم الحالي سجل في جدول المرضى بعد، ننشئه له تلقائياً
        if not patient:
            patient = request.env['dawai.patient'].sudo().create({
                'pat_name': current_user.name,
                'user_id': current_user.id,
            })

        error_msg = False

        # معالجة الضغط على زر "تأكيد الحجز النهائي" (POST)
        if request.httprequest.method == 'POST':
            qty_booked = int(kwargs.get('qty_booked', 1))
            try:
                # إنشاء السجل في جدول حجز الأدوية (جدول 7)
                booking = request.env['dawai.medicine.booking'].sudo().create({
                    'pat_id': patient.id,
                    'stock_id': inventory.id,
                    'qty_booked': qty_booked,
                })
                # عند النجاح الكامل، يتم توجيه المريض مباشرة إلى صفحة النجاح وعرض الكود له
                return request.render('dawai_platform.booking_success_template', {
                    'booking': booking
                })
            except ValidationError as e:
                # في حال كسر أحد الشروط (مثال: حجز نشط مسبقاً)، نلتقط الخطأ ونعرضه للمريض بوضوح في الواجهة
                error_msg = str(e)

        return request.render('dawai_platform.booking_confirmation_template', {
            'inventory': inventory,
            'current_user': current_user,
            'error_msg': error_msg
        })

    # 4. بوابة المريض - شاشة (حجوزاتي الطبية)
    @http.route('/my/bookings', type='http', auth='user', website=True)
    def patient_my_bookings(self, **kwargs):
        current_user = request.env.user

        # البحث عن المريض المرتبط بالحساب الحالي
        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', current_user.id)], limit=1)

        # جلب الحجوزات وترتيبها من الأحدث للأقدم
        bookings = request.env['dawai.medicine.booking']
        if patient:
            bookings = request.env['dawai.medicine.booking'].sudo().search([
                ('pat_id', '=', patient.id)
            ], order='booking_date desc')

        return request.render('dawai_platform.patient_my_bookings_template', {
            'bookings': bookings,
        })