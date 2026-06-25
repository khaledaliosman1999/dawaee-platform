# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class DawaiPharmacyPortal(http.Controller):

    # ── 1. الشاشة الرئيسية (لوحة تحكم الصيدلية) ──
    @http.route(['/my/pharmacy'], type='http', auth="user", website=True)
    def pharmacy_dashboard(self, **kw):
        user = request.env.user

        # التأكد أن المستخدم مربوط بصيدلية
        if not user.pharmacy_id:
            return request.render('dawaee_platform.portal_pharmacist_error', {
                'message': 'عفواً، حسابك الحالي غير مربوط بأي صيدلية. يرجى مراجعة إدارة النظام لتفعيل حسابك كصيدلاني.'
            })

        # جلب حجوزات هذه الصيدلية "فقط"
        active_bookings = request.env['dawai.medicine.booking'].sudo().search([
            ('status', '=', 'active'),
            ('pharm_id', '=', user.pharmacy_id.id)
        ])

        return request.render('dawaee_platform.portal_pharmacist_dashboard', {
            'bookings': active_bookings,
            'pharmacy_name': user.pharmacy_id.pharm_name,
        })

    # ── 2. شاشة الصرف السريع وتوليد الوصفة ──
    @http.route(['/my/pharmacy/dispense/<int:booking_id>'], type='http', auth="user", website=True,
                methods=['GET', 'POST'])
    def dispense_booking_web(self, booking_id, **kw):
        user = request.env.user
        booking = request.env['dawai.medicine.booking'].sudo().browse(booking_id)

        # حماية إضافية: منع صرف حجز يتبع لصيدلية أخرى
        if booking.pharm_id.id != user.pharmacy_id.id:
            return request.redirect('/my/pharmacy')

        if request.httprequest.method == 'POST':

            # أ. إذا كان الدواء يحتاج وصفة، نأخذ البيانات المدخلة وننشئ وصفة في الجدول
            if booking.med_id.requires_prescription:
                request.env['dawai.prescription'].sudo().create({
                    'booking_id': booking.id,
                    'doctor_name': kw.get('doctor_name'),
                    'allowed_qty': int(kw.get('allowed_qty', booking.qty_booked)),
                })

            # ب. إنشاء حركة الصرف
            request.env['dawai.dispensing.transaction'].sudo().create({
                'booking_id': booking.id,
                'qty_dispensed': booking.qty_booked,
                'unit_price': booking.unit_price_at_booking,
            })

            # ج. تحديث حالة الحجز إلى "تم الصرف"
            booking.sudo().write({'status': 'dispensed'})
            return request.redirect('/my/pharmacy?success=dispensed')

        # إذا كان الطلب GET، نفتح الشاشة للصيدلي
        return request.render('dawaee_platform.portal_dispense_form', {
            'booking': booking
        })

    # ── 3. شاشة تسجيل الوارد للمخزون ──
    @http.route(['/my/pharmacy/inventory/inbound'], type='http', auth="user", website=True, methods=['GET', 'POST'])
    def pharmacy_inventory_inbound(self, **kw):
        user = request.env.user

        # حماية
        if not user.pharmacy_id:
            return request.redirect('/my/pharmacy')

        if request.httprequest.method == 'POST':
            med_id = int(kw.get('med_id'))
            qty_received = int(kw.get('qty_received', 0))
            unit_price = float(kw.get('unit_price', 0.0))

            if qty_received > 0:
                # البحث في مخزون هذه الصيدلية تحديداً
                inventory = request.env['dawai.inventory'].sudo().search([
                    ('pharm_id', '=', user.pharmacy_id.id),
                    ('med_id', '=', med_id)
                ], limit=1)

                if inventory:
                    # تحديث الكمية والسعر إذا كان الدواء موجوداً
                    inventory.sudo().write({
                        'qty_available': inventory.qty_available + qty_received,
                        'unit_price': unit_price
                    })
                else:
                    # إضافة دواء جديد لمخزون الصيدلية
                    request.env['dawai.inventory'].sudo().create({
                        'pharm_id': user.pharmacy_id.id,
                        'med_id': med_id,
                        'qty_available': qty_received,
                        'unit_price': unit_price,
                        'active': True
                    })
            # إعادة توجيه مع رسالة نجاح
            return request.redirect('/my/pharmacy/inventory/inbound?success=1')

        # جلب الأدوية لعرضها في القائمة المنسدلة
        medicines = request.env['dawai.medicine'].sudo().search([('active', '=', True)])
        # جلب المخزون الحالي للصيدلية لعرضه أسفل الشاشة
        current_inventory = request.env['dawai.inventory'].sudo().search([
            ('pharm_id', '=', user.pharmacy_id.id)
        ])

        return request.render('dawaee_platform.portal_inventory_inbound', {
            'pharmacy_name': user.pharmacy_id.pharm_name,
            'medicines': medicines,
            'inventory_items': current_inventory,
            'success': kw.get('success')
        })

    @http.route(['/my/pharmacy/inventory/current'], type='http', auth="user", website=True)
    def pharmacy_inventory_current(self, **kw):
        user = request.env.user

        # حماية
        if not user.pharmacy_id:
            return request.redirect('/my/pharmacy')

        # جلب كل المخزون
        inventory_items = request.env['dawai.inventory'].sudo().search([
            ('pharm_id', '=', user.pharmacy_id.id)
        ])

        total_qty = sum(item.qty_available for item in inventory_items)

        return request.render('dawaee_platform.portal_inventory_current', {
            'pharmacy_name': user.pharmacy_id.pharm_name,
            'inventory_items': inventory_items,
            'total_qty': total_qty,
        })

    # ── 6. شاشة سجل الصرف (History) ──
    @http.route(['/my/pharmacy/history'], type='http', auth="user", website=True)
    def pharmacy_dispense_history(self, **kw):
        user = request.env.user

        if not user.pharmacy_id:
            return request.redirect('/my/pharmacy')

        # جلب الحجوزات الخاصة بالصيدلية (هنا نفترض أننا نجلب كل الحجوزات للعرض، يمكنك لاحقاً فلترتها بالحالة "تم الصرف")
        history_bookings = request.env['dawai.medicine.booking'].sudo().search([
            ('pharm_id', '=', user.pharmacy_id.id)
        ], order='create_date desc', limit=50)  # نعرض آخر 50 عملية مرتبة من الأحدث للأقدم

        return request.render('dawaee_platform.portal_dispense_history', {
            'pharmacy_name': user.pharmacy_id.pharm_name,
            'history_bookings': history_bookings,
        })

    # ── 7. شاشة الوصفات الطبية (Prescriptions Archive) ──
    @http.route(['/my/pharmacy/prescriptions'], type='http', auth="user", website=True)
    def pharmacy_prescriptions_list(self, **kw):
        user = request.env.user

        # حماية المسار
        if not user.pharmacy_id:
            return request.redirect('/my/pharmacy')

        # جلب الحجوزات التي تم صرفها وتتطلب وصفة طبية (أدوية مقيدة)
        # يمكنك تعديل حالة البحث (state) لاحقاً لتشمل فقط "تم الصرف"
        prescriptions = request.env['dawai.medicine.booking'].sudo().search([
            ('pharm_id', '=', user.pharmacy_id.id),
            ('med_id.requires_prescription', '=', True)
        ], order='create_date desc', limit=50)

        return request.render('dawaee_platform.portal_prescriptions_list', {
            'pharmacy_name': user.pharmacy_id.pharm_name,
            'prescriptions': prescriptions,
        })