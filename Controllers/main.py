# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

class DawaiPortal(http.Controller):

    @http.route('/dawai', auth='public', type='http', website=True)
    def home(self, **kwargs):
        return request.redirect('/dawai/search')

    @http.route('/dawai/search', auth='public', type='http', website=True, methods=['GET'])
    def search_medicine(self, query='', **kwargs):
        inventories = request.env['dawai.inventory'].sudo()
        domain = [('qty_net', '>', 0), ('active', '=', True)]

        if query:
            domain += ['|', ('med_id.med_name', 'ilike', query), ('med_id.scientific_name', 'ilike', query)]

        results = inventories.search(domain, order='unit_price asc')

        medicines_map = {}
        for inv in results:
            med_id = inv.med_id.id
            if med_id not in medicines_map:
                medicines_map[med_id] = {
                    'medicine': inv.med_id,
                    'pharmacies': [],
                }
            medicines_map[med_id]['pharmacies'].append(inv)

        return request.render('dawaee_platform.portal_search_page', {
            'query':        query,
            'results_map':  medicines_map,
            'total_count':  len(results),
        })

    @http.route('/dawai/medicine/<int:stock_id>', auth='public', type='http', website=True)
    def medicine_detail(self, stock_id, **kwargs):
        stock = request.env['dawai.inventory'].sudo().browse(stock_id)
        if not stock.exists() or not stock.active:
            return request.redirect('/dawai/search')

        other_pharmacies = request.env['dawai.inventory'].sudo().search([
            ('med_id', '=', stock.med_id.id),
            ('qty_net', '>', 0),
            ('active', '=', True),
            ('id', '!=', stock_id),
        ], order='unit_price asc')

        return request.render('dawaee_platform.portal_medicine_detail', {
            'stock':            stock,
            'other_pharmacies': other_pharmacies,
        })

    @http.route('/dawai/book/<int:stock_id>', auth='user', type='http', website=True, methods=['GET'])
    def booking_form(self, stock_id, **kwargs):
        stock = request.env['dawai.inventory'].sudo().browse(stock_id)
        if not stock.exists() or stock.qty_net <= 0:
            return request.redirect('/dawai/search')

        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if not patient:
            patient = request.env['dawai.patient'].sudo().create({
                'pat_name': request.env.user.name,
                'email':    request.env.user.email or '',
                'user_id':  request.env.user.id,
            })

        existing_booking = request.env['dawai.medicine.booking'].sudo().search([
            ('pat_id',  '=', patient.id),
            ('med_id',  '=', stock.med_id.id),
            ('status',  '=', 'active'),
        ], limit=1)

        return request.render('dawaee_platform.portal_booking_form', {
            'stock':            stock,
            'patient':          patient,
            'existing_booking': existing_booking,
        })

    @http.route('/dawai/book/confirm', auth='user', type='http', website=True, methods=['POST'])
    def booking_confirm(self, stock_id, qty=1, **kwargs):
        try:
            stock_id = int(stock_id)
            qty = int(qty)
        except (ValueError, TypeError):
            return request.redirect('/dawai/search')

        stock = request.env['dawai.inventory'].sudo().browse(stock_id)
        if not stock.exists() or stock.qty_net < qty:
            return request.render('dawaee_platform.portal_booking_result', {
                'success': False,
                'error':   'الكمية المطلوبة غير متوفرة في المخزون',
                'stock':   stock,
            })

        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if not patient:
            return request.redirect('/dawai/search')

        try:
            booking = request.env['dawai.medicine.booking'].sudo().create({
                'pat_id':    patient.id,
                'stock_id':  stock_id,
                'qty_booked': qty,
            })
            return request.render('dawaee_platform.portal_booking_result', {
                'success':      True,
                'booking':      booking,
                'stock':        stock,
            })
        except ValidationError as e:
            return request.render('dawaee_platform.portal_booking_result', {
                'success': False,
                'error':   str(e),
                'stock':   stock,
            })

    @http.route('/dawai/my-bookings', auth='user', type='http', website=True)
    def my_bookings(self, **kwargs):
        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)

        if not patient:
            return request.redirect('/dawai/search')

        bookings = request.env['dawai.medicine.booking'].sudo().search([
            ('pat_id', '=', patient.id),
        ], order='booking_date desc')

        return request.render('dawaee_platform.portal_my_bookings', {
            'patient':  patient,
            'bookings': bookings,
        })

    @http.route('/dawai/booking/cancel/<int:booking_id>', auth='user', type='http', website=True, methods=['POST'])
    def cancel_booking(self, booking_id, **kwargs):
        patient = request.env['dawai.patient'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
        booking = request.env['dawai.medicine.booking'].sudo().browse(booking_id)

        if (booking.exists() and patient and booking.pat_id.id == patient.id and booking.status == 'active'):
            try:
                booking.action_cancel()
            except ValidationError:
                pass

        return request.redirect('/dawai/my-bookings')