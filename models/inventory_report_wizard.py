# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api


class InventoryReportWizard(models.TransientModel):
    _name = 'inventory.report.wizard'
    _description = 'معالج تقرير المخزون الحالي'

    pharmacy_id = fields.Many2one('dawai.pharmacy', string="الصيدلية")
    is_readonly_pharmacy = fields.Boolean(compute='_compute_readonly_pharmacy')
    low_stock_only = fields.Boolean(
        string="عرض المخزون المنخفض فقط",
        default=False,
        help="عرض الأدوية التي وصلت كميتها للحد الأدنى للتنبيه فقط",
    )
    order_type = fields.Selection([
        ('lowest', 'الأقل كمية أولاً (أولوية التوريد)'),
        ('highest', 'الأعلى كمية أولاً'),
        ('name', 'أبجدياً حسب اسم الدواء'),
    ], string="الترتيب", default='lowest', required=True)

    @api.depends('pharmacy_id')
    def _compute_readonly_pharmacy(self):
        is_admin = self.env.user.has_group('dawaee_platform.group_dawai_admin')
        for rec in self:
            rec.is_readonly_pharmacy = not is_admin

    @api.model
    def default_get(self, fields_list):
        res = super(InventoryReportWizard, self).default_get(fields_list)
        if 'pharmacy_id' in fields_list and self.env.user.pharmacy_id:
            res['pharmacy_id'] = self.env.user.pharmacy_id.id
        return res

    def action_print_report(self):
        domain = [('active', '=', True)]
        if self.pharmacy_id:
            domain.append(('pharm_id', '=', self.pharmacy_id.id))
        if self.low_stock_only:
            domain.append(('is_low_stock', '=', True))

        if self.order_type == 'lowest':
            order_str = 'qty_available asc'
        elif self.order_type == 'highest':
            order_str = 'qty_available desc'
        else:
            order_str = 'med_id asc'

        records = self.env['dawai.inventory'].search(domain, order=order_str)

        report = self.env.ref('dawaee_platform.action_report_inventory')
        pdf_content, _ = report._render_qweb_pdf(
            'dawaee_platform.report_inventory_template',
            res_ids=records.ids,
            data={
                'pharmacy_name': self.pharmacy_id.pharm_name if self.pharmacy_id else 'كل الصيدليات',
                'low_stock_only': self.low_stock_only,
            }
        )

        attachment = self.env['ir.attachment'].create({
            'name': 'تقرير_المخزون.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'inventory.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
