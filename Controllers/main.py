# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError, AccessDenied

_logger = logging.getLogger(__name__)


class DawaiPortal(http.Controller):

    @http.route('/dawai', auth='public', type='http', website=True)
    def home(self, **kwargs):
        return request.redirect('/dawai/search')

    # ══ البحث العام ══════════════════════════════════════
    @http.route('/dawai/search', auth='public', type='http', website=True, methods=['GET'])
    def search_medicine(self, query='', category='', **kwargs):
        domain = [('qty_net', '>', 0), ('active', '=', True)]
        if query:
            domain.append(('med_id.med_name', 'ilike', query))
        if category:
            domain.append(('med_id.med_category', '=', category))

        results = request.env['dawai.inventory'].sudo().search(domain, order='unit_price asc')

        medicines_map = {}
        for inv in results:
            mid = inv.med_id.id
            if mid not in medicines_map:
                medicines_map[mid] = {'medicine': inv.med_id, 'pharmacies': []}
            medicines_map[mid]['pharmacies'].append(inv)

        return request.render('dawaee_platform.portal_search_page', {
            'query': query, 'category': category,
            'results_map': medicines_map, 'total_count': len(results),
            'categories': [
                ('diabetes', 'سكري'), ('pressure', 'ضغط دم'),
                ('heart', 'قلب'), ('asthma', 'ربو'),
                ('rare', 'نادر'), ('emergency', 'طوارئ'),
            ],
        })

    # ══ بوابة الحجز — اختيار تسجيل أو دخول ═════════════
    @http.route('/dawai/book/<int:stock_id>', auth='public', type='http', website=True, methods=['GET'])
    def booking_gate(self, stock_id, **kwargs):
        stock = request.env['dawai.inventory'].sudo().browse(stock_id)
        if not stock.exists() or stock.qty_net <= 0:
            return request.redirect('/dawai/search')

        if not request.env.user._is_public():
            return request.redirect('/dawai/book/%d/confirm-form' % stock_id)

        return request.render('dawaee_platform.portal_auth_gate', {
            'stock': stock,
            'next': '/dawai/book/%d/confirm-form' % stock_id,
        })

    # ══ تسجيل مريض جديد (GET) ════════════════════════════
    @http.route('/dawai/register', auth='public', type='http', website=True, methods=['GET'])
    def register_form(self, next='/dawai/my-bookings', **kwargs):
        if not request.env.user._is_public():
            return request.redirect(next)
        return request.render('dawaee_platform.portal_register_page', {
            'next': next, 'errors': {}, 'values': {},
            'disease_types': [
                ('diabetes', 'سكري'), ('pressure', 'ضغط دم'),
                ('heart', 'قلب'), ('asthma', 'ربو'), ('other', 'أخرى'),
            ],
        })

    # ══ تسجيل مريض جديد (POST) ═══════════════════════════
    @http.route('/dawai/register', auth='public', type='http', website=True, methods=['POST'])
    def register_submit(self, **post):
        national_id = post.get('national_id', '').strip()
        pat_name = post.get('pat_name', '').strip()
        disease_type = post.get('disease_type', '')
        contact_info = post.get('contact_info', '').strip()
        email = post.get('email', '').strip()
        next_url = post.get('next', '/dawai/my-bookings')

        errors = {}
        values = {
            'national_id': national_id, 'pat_name': pat_name,
            'disease_type': disease_type,
            'contact_info': contact_info, 'email': email,
        }
        disease_types = [
            ('diabetes', 'سكري'), ('pressure', 'ضغط دم'),
            ('heart', 'قلب'), ('asthma', 'ربو'), ('other', 'أخرى'),
        ]

        def render_form(errs):
            return request.render('dawaee_platform.portal_register_page', {
                'next': next_url, 'errors': errs,
                'values': values, 'disease_types': disease_types,
            })

        # ── تحقق من المدخلات ──
        if not national_id:
            errors['national_id'] = 'الرقم الوطني مطلوب'
        elif not national_id.isdigit():
            errors['national_id'] = 'يجب أن يحتوي على أرقام فقط'
        elif len(national_id) != 11:
            errors['national_id'] = 'يجب أن يكون 11 رقماً بالضبط'
        if not pat_name:
            errors['pat_name'] = 'الاسم الكامل مطلوب'
        if errors:
            return render_form(errors)

        # ── هل مسجل مسبقاً؟ ──
        existing = request.env['res.users'].sudo().search([('login', '=', national_id)], limit=1)
        if existing:
            try:
                # المصادقة رقم 1: (تمت إضافة نوع كلمة المرور هنا)
                uid = request.session.authenticate(request.db, {
                    'login': national_id,
                    'password': national_id,
                    'type': 'password'
                })
                if uid:
                    return request.redirect(next_url)
            except AccessDenied:
                pass
            except Exception as e:
                errors['general'] = 'خطأ في المصادقة: %s' % str(e)
                return render_form(errors)

            errors['national_id'] = 'هذا الرقم مسجل — جرّب تسجيل الدخول'
            return render_form(errors)

        # ── إنشاء حساب جديد ──
        try:
            new_user = request.env['res.users'].sudo().create({
                'name': pat_name,
                'login': national_id,
                'password': national_id,
                'email': email or False,
            })
            request.env['dawai.patient'].sudo().create({
                'pat_name': pat_name,
                'national_id': national_id,
                'disease_type': disease_type or False,
                'contact_info': contact_info or False,
                'email': email or False,
                'user_id': new_user.id,
                'active': True,
            })

            # حفظ التغييرات في قاعدة البيانات أولاً لتستطيع المصادقة العثور على المستخدم
            request.env.cr.commit()

            # المصادقة رقم 2: (تمت إضافة نوع كلمة المرور هنا أيضاً)
            uid = request.session.authenticate(request.db, {
                'login': national_id,
                'password': national_id,
                'type': 'password'
            })
            if uid:
                return request.redirect(next_url)

        except Exception as e:
            _logger.error('Dawai register error: %s', e)
            errors['general'] = 'حدث خطأ: %s' % str(e)
            return render_form(errors)

        return request.redirect(next_url)

    # ══ تسجيل دخول مريض موجود (GET) ═════════════════════
    @http.route('/dawai/login', auth='public', type='http', website=True, methods=['GET'])
    def login_form(self, next='/dawai/my-bookings', **kwargs):
        if not request.env.user._is_public():
            return request.redirect(next)
        return request.render('dawaee_platform.portal_login_page', {
            'next': next, 'errors': {},
        })

    # ══ تسجيل دخول مريض موجود (POST) ════════════════════
    @http.route('/dawai/login', auth='public', type='http', website=True, methods=['POST'])
    def login_submit(self, **post):
        national_id = post.get('national_id', '').strip()
        next_url = post.get('next', '/dawai/my-bookings')
        errors = {}

        if not national_id:
            errors['national_id'] = 'الرقم الوطني مطلوب'
        elif not national_id.isdigit() or len(national_id) != 11:
            errors['national_id'] = 'رقم غير صحيح — يجب 11 رقماً'

        if not errors:
            try:
                # المصادقة رقم 3: (تمت إضافة نوع كلمة المرور هنا أيضاً)
                uid = request.session.authenticate(request.db, {
                    'login': national_id,
                    'password': national_id,
                    'type': 'password'
                })
                if uid:
                    return request.redirect(next_url)
                errors['national_id'] = 'الرقم غير مسجل — سجّل أولاً'
            except AccessDenied:
                errors['national_id'] = 'فشل الدخول — تأكد من رقمك'
            except Exception as e:
                errors['national_id'] = 'خطأ في النظام: %s' % str(e)

        return request.render('dawaee_platform.portal_login_page', {
            'next': next_url, 'errors': errors,
        })

    # ══ صفحة تأكيد الحجز (بعد الدخول) ══════════════════
    @http.route('/dawai/book/<int:stock_id>/confirm-form', auth='user', type='http', website=True, methods=['GET'])
    def booking_confirm_form(self, stock_id, **kwargs):
        stock = request.env['dawai.inventory'].sudo().browse(stock_id)
        if not stock.exists() or stock.qty_net <= 0:
            return request.redirect('/dawai/search')

        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        if not patient:
            return request.redirect('/dawai/register?next=/dawai/book/%d/confirm-form' % stock_id)

        existing_booking = request.env['dawai.medicine.booking'].sudo().search([
            ('pat_id', '=', patient.id),
            ('med_id', '=', stock.med_id.id),
            ('status', '=', 'active'),
        ], limit=1)

        return request.render('dawaee_platform.portal_booking_form', {
            'stock': stock, 'patient': patient,
            'existing_booking': existing_booking,
        })

    # ══ تنفيذ الحجز (POST) ════════════════════════════════
    @http.route('/dawai/book/confirm', auth='user', type='http', website=True, methods=['POST'])
    def booking_confirm(self, stock_id, qty=1, **kwargs):
        try:
            stock_id = int(stock_id)
            qty = max(1, int(qty))
        except (ValueError, TypeError):
            return request.redirect('/dawai/search')

        stock = request.env['dawai.inventory'].sudo().browse(stock_id)
        if not stock.exists() or stock.qty_net < qty:
            return request.render('dawaee_platform.portal_booking_result', {
                'success': False,
                'error': 'الكمية المطلوبة غير متوفرة في المخزون',
                'stock': stock,
            })

        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        if not patient:
            return request.redirect('/dawai/search')

        try:
            booking = request.env['dawai.medicine.booking'].sudo().create({
                'pat_id': patient.id,
                'stock_id': stock_id,
                'qty_booked': qty,
            })
            return request.render('dawaee_platform.portal_booking_result', {
                'success': True, 'booking': booking, 'stock': stock,
            })
        except (ValidationError, Exception) as e:
            return request.render('dawaee_platform.portal_booking_result', {
                'success': False, 'error': str(e), 'stock': stock,
            })

    # ══ حجوزاتي ══════════════════════════════════════════
    @http.route('/dawai/my-bookings', auth='user', type='http', website=True)
    def my_bookings(self, **kwargs):
        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        if not patient:
            return request.redirect('/dawai/search')

        bookings = request.env['dawai.medicine.booking'].sudo().search(
            [('pat_id', '=', patient.id)], order='booking_date desc')

        return request.render('dawaee_platform.portal_my_bookings', {
            'patient': patient, 'bookings': bookings,
        })

    # ══ إلغاء حجز ════════════════════════════════════════
    @http.route('/dawai/booking/cancel/<int:booking_id>', auth='user', type='http', website=True, methods=['POST'])
    def cancel_booking(self, booking_id, **kwargs):
        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        booking = request.env['dawai.medicine.booking'].sudo().browse(booking_id)

        if (patient and booking.exists() and
                booking.pat_id.id == patient.id and
                booking.status == 'active'):
            try:
                booking.action_cancel()
            except ValidationError:
                pass
        return request.redirect('/dawai/my-bookings')