# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api


class PrescriptionReportWizard(models.TransientModel):
    _name = 'prescription.report.wizard'
    _description = 'معالج تقرير الوصفات الطبية'

    date_start = fields.Date(string="من تاريخ (تاريخ الإصدار)")
    date_end = fields.Date(string="إلى تاريخ (تاريخ الإصدار)", default=fields.Date.context_today)
    low_remaining_only = fields.Boolean(
        string="عرض الوصفات القريبة من الاستنفاد فقط",
        default=False,
        help="عرض الوصفات التي تبقى لها مرة صرف واحدة أو أقل",
    )
    valid_only = fields.Boolean(string="عرض الوصفات السارية فقط", default=False)
    order_type = fields.Selection([
        ('remaining_asc', 'الأقل مرات متبقية أولاً (أولوية المتابعة)'),
        ('remaining_desc', 'الأكثر مرات متبقية أولاً'),
        ('issue_date', 'حسب تاريخ الإصدار'),
    ], string="الترتيب", default='remaining_asc', required=True)

    def action_print_report(self):
        domain = []
        if self.date_start:
            domain.append(('issue_date', '>=', self.date_start))
        if self.date_end:
            domain.append(('issue_date', '<=', self.date_end))
        if self.low_remaining_only:
            domain.append(('qty_remaining', '<=', 1))
        if self.valid_only:
            domain.append(('is_valid', '=', True))

        if self.order_type == 'remaining_asc':
            order_str = 'qty_remaining asc'
        elif self.order_type == 'remaining_desc':
            order_str = 'qty_remaining desc'
        else:
            order_str = 'issue_date desc'

        records = self.env['dawai.prescription'].search(domain, order=order_str)

        report = self.env.ref('dawaee_platform.action_report_prescription')
        pdf_content, _ = report._render_qweb_pdf(
            'dawaee_platform.report_prescription_template',
            res_ids=records.ids,
            data={
                'low_remaining_only': self.low_remaining_only,
                'valid_only': self.valid_only,
            }
        )

        attachment = self.env['ir.attachment'].create({
            'name': 'تقرير_الوصفات_الطبية.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'prescription.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
