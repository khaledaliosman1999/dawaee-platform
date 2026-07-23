# -*- coding: utf-8 -*-
import base64
from datetime import datetime, time

from odoo import models, fields, api


class MedicineDemandReportWizard(models.TransientModel):
    _name = 'medicine.demand.report.wizard'
    _description = 'معالج تقرير الأدوية الأكثر / الأقل طلباً'

    order_type = fields.Selection([
        ('most', 'الأكثر طلباً (لزيادة الاستيراد)'),
        ('least', 'الأقل طلباً (لتقليل الاستيراد)'),
    ], string="نوع التقرير", default='most', required=True)

    date_start = fields.Date(string="من تاريخ")
    date_end = fields.Date(string="إلى تاريخ", default=fields.Date.context_today)
    pharmacy_id = fields.Many2one('dawai.pharmacy', string="الصيدلية")
    is_readonly_pharmacy = fields.Boolean(compute='_compute_readonly_pharmacy')
    limit = fields.Integer(string="عدد الأدوية المعروضة", default=10)

    @api.depends('pharmacy_id')
    def _compute_readonly_pharmacy(self):
        is_admin = self.env.user.has_group('dawaee_platform.group_dawai_admin')
        for rec in self:
            rec.is_readonly_pharmacy = not is_admin

    @api.model
    def default_get(self, fields_list):
        res = super(MedicineDemandReportWizard, self).default_get(fields_list)
        if 'pharmacy_id' in fields_list and self.env.user.pharmacy_id:
            res['pharmacy_id'] = self.env.user.pharmacy_id.id
        return res

    def action_print_report(self):
        domain = []
        if self.date_start:
            domain.append(('dispense_date', '>=', datetime.combine(self.date_start, time.min)))
        if self.date_end:
            domain.append(('dispense_date', '<=', datetime.combine(self.date_end, time.max)))
        if self.pharmacy_id:
            domain.append(('pharm_id', '=', self.pharmacy_id.id))

        order_str = 'qty_dispensed desc' if self.order_type == 'most' else 'qty_dispensed asc'

        grouped = self.env['dawai.dispensing.transaction'].read_group(
            domain,
            ['qty_dispensed:sum', 'total_price:sum'],
            ['med_id'],
            orderby=order_str,
            limit=self.limit,
        )

        lines = []
        for g in grouped:
            med = self.env['dawai.medicine'].browse(g['med_id'][0]) if g['med_id'] else False
            lines.append({
                'med_name': med.med_name if med else 'غير معروف',
                'qty_total': g.get('qty_dispensed', 0),
                'total_price': g.get('total_price', 0.0),
                'transactions_count': g.get('med_id_count', 0),
            })

        report = self.env.ref('dawaee_platform.action_report_medicine_demand')
        pdf_content, _ = report._render_qweb_pdf(
            'dawaee_platform.report_medicine_demand_template',
            res_ids=self.ids,
            data={
                'lines': lines,
                'order_type': self.order_type,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'pharmacy_name': self.pharmacy_id.pharm_name if self.pharmacy_id else 'كل الصيدليات',
            }
        )

        attachment = self.env['ir.attachment'].create({
            'name': 'تقرير_طلب_الأدوية.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'medicine.demand.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
