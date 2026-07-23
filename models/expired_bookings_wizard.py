# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api


class ExpiredBookingsReportWizard(models.TransientModel):
    _name = 'expired.bookings.report.wizard'
    _description = 'معالج تقرير الحجوزات المنتهية المهلة'

    date_start = fields.Date(string="من تاريخ")
    date_end = fields.Date(string="إلى تاريخ", default=fields.Date.context_today)
    pharmacy_id = fields.Many2one('dawai.pharmacy', string="الصيدلية")
    is_readonly_pharmacy = fields.Boolean(compute='_compute_readonly_pharmacy')
    status_filter = fields.Selection([
        ('expired', 'المنتهية فقط (لم تُستلم خلال 24 ساعة)'),
        ('cancelled', 'الملغية فقط (ألغاها المريض)'),
        ('both', 'المنتهية + الملغية (إجمالي الفاقد)'),
    ], string="نوع الفاقد", default='both', required=True)

    @api.depends('pharmacy_id')
    def _compute_readonly_pharmacy(self):
        is_admin = self.env.user.has_group('dawaee_platform.group_dawai_admin')
        for rec in self:
            rec.is_readonly_pharmacy = not is_admin

    @api.model
    def default_get(self, fields_list):
        res = super(ExpiredBookingsReportWizard, self).default_get(fields_list)
        if 'pharmacy_id' in fields_list and self.env.user.pharmacy_id:
            res['pharmacy_id'] = self.env.user.pharmacy_id.id
        return res

    def action_print_report(self):
        if self.status_filter == 'both':
            domain = [('status', 'in', ['expired', 'cancelled'])]
        else:
            domain = [('status', '=', self.status_filter)]

        if self.date_start:
            domain.append(('booking_date', '>=', self.date_start))
        if self.date_end:
            domain.append(('booking_date', '<=', self.date_end))
        if self.pharmacy_id:
            domain.append(('pharm_id', '=', self.pharmacy_id.id))

        records = self.env['dawai.medicine.booking'].search(domain, order='booking_date desc')

        # لحساب نسبة الفاقد نحتاج إجمالي كل الحجوزات في نفس النطاق
        total_domain = []
        if self.date_start:
            total_domain.append(('booking_date', '>=', self.date_start))
        if self.date_end:
            total_domain.append(('booking_date', '<=', self.date_end))
        if self.pharmacy_id:
            total_domain.append(('pharm_id', '=', self.pharmacy_id.id))
        total_count = self.env['dawai.medicine.booking'].search_count(total_domain)
        loss_percentage = (len(records) / total_count * 100) if total_count else 0.0

        report = self.env.ref('dawaee_platform.action_report_expired_bookings')
        pdf_content, _ = report._render_qweb_pdf(
            'dawaee_platform.report_expired_bookings_template',
            res_ids=records.ids,
            data={
                'pharmacy_name': self.pharmacy_id.pharm_name if self.pharmacy_id else 'كل الصيدليات',
                'status_filter': self.status_filter,
                'total_count': total_count,
                'loss_percentage': loss_percentage,
            }
        )

        attachment = self.env['ir.attachment'].create({
            'name': 'تقرير_الحجوزات_الفاقدة.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'expired.bookings.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
