import base64
from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api


class DispensingReportWizard(models.TransientModel):
    _name = 'dispensing.report.wizard'
    _description = 'معالج تقارير الصرف'

    report_type = fields.Selection([
        ('daily', 'يومي'),
        ('weekly', 'أسبوعي'),
        ('monthly', 'شهري'),
        ('yearly', 'سنوي'),
        ('custom', 'تحديد التاريخ يدوياً')
    ], string="نوع الفترة", default='daily', required=True)
    date_start = fields.Date(string="من تاريخ")
    date_end = fields.Date(string="إلى تاريخ", default=fields.Date.context_today)
    pharmacy_id = fields.Many2one('dawai.pharmacy', string="الصيدلية")
    is_readonly_pharmacy = fields.Boolean(compute='_compute_readonly_pharmacy')

    @api.depends('pharmacy_id')
    def _compute_readonly_pharmacy(self):
        is_admin = self.env.user.has_group('dawaee_platform.group_dawai_admin')
        for rec in self:
            rec.is_readonly_pharmacy = not is_admin

    @api.model
    def default_get(self, fields_list):
        res = super(DispensingReportWizard, self).default_get(fields_list)
        if 'pharmacy_id' in fields_list and self.env.user.pharmacy_id:
            res['pharmacy_id'] = self.env.user.pharmacy_id.id
        return res

    def action_print_report(self):
        domain = []
        today = fields.Date.context_today(self)

        if self.report_type == 'custom':
            start, end = self.date_start, self.date_end
        elif self.report_type == 'daily':
            start = end = today
        elif self.report_type == 'weekly':
            start, end = today - timedelta(days=7), today
        elif self.report_type == 'monthly':
            start, end = today - relativedelta(months=1), today
        elif self.report_type == 'yearly':
            start, end = today - relativedelta(years=1), today
        else:
            start = end = False

        if start:
            domain.append(('dispense_date', '>=', datetime.combine(start, time.min)))
        if end:
            domain.append(('dispense_date', '<=', datetime.combine(end, time.max)))
        if self.pharmacy_id:
            domain.append(('pharm_id', '=', self.pharmacy_id.id))

        records = self.env['dawai.dispensing.transaction'].search(domain)

        report = self.env.ref('dawaee_platform.action_report_dispensing')
        pdf_content, _ = report._render_qweb_pdf(
            'dawaee_platform.report_dispensing_template',
            res_ids=records.ids
        )

        attachment = self.env['ir.attachment'].create({
            'name': 'تقرير_الصرف.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'dispensing.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
