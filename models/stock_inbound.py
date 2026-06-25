# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiStockInbound(models.Model):
    _name = 'dawai.stock.inbound'
    _description = 'جدول توريد المخزن'
    _rec_name = 'display_name'
    _order = 'in_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    supplier_id = fields.Many2one(
        'dawai.supplier', string='المورد',
        required=True, ondelete='restrict', tracking=True,
    )
    pharm_id = fields.Many2one(
        'dawai.pharmacy', string='الصيدلية المستلِمة',
        required=True, ondelete='restrict', tracking=True,
    )
    med_id = fields.Many2one(
        'dawai.medicine', string='الدواء',
        required=True, ondelete='restrict', tracking=True,
    )
    qty_in = fields.Integer(
        string='الكمية الواردة', required=True, tracking=True,
    )
    in_date = fields.Date(
        string='تاريخ دخول الشحنة',
        default=fields.Date.today, required=True, tracking=True,
    )
    batch_no = fields.Char(string='رقم الدفعة', size=20, tracking=True)

    # ── سعر البيع في هذه الصيدلية ───────────────────────
    unit_price = fields.Float(
        string='سعر البيع في الصيدلية (SDG)',
        digits=(10, 2),
        default=0.0,
        tracking=True,
        help='السعر الذي ستبيعه الصيدلية للمريض — يُنسخ تلقائياً للمخزون',
    )

    state = fields.Selection(
        selection=[
            ('draft', 'مسودة'),
            ('confirmed', 'مؤكدة'),
            ('done', 'مُعالَجة'),
        ],
        default='draft', tracking=True, readonly=True,
    )
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('med_id', 'pharm_id', 'in_date')
    def _compute_display_name(self):
        for rec in self:
            med = rec.med_id.med_name if rec.med_id else '—'
            phm = rec.pharm_id.pharm_name if rec.pharm_id else '—'
            date = str(rec.in_date) if rec.in_date else '—'
            rec.display_name = f'[{date}] {med} ← {phm}'

    def action_confirm_and_update_inventory(self):
        for rec in self:
            if rec.state == 'done':
                raise ValidationError('هذه الشحنة تمت معالجتها بالفعل!')

            inventory = self.env['dawai.inventory'].search([
                ('pharm_id', '=', rec.pharm_id.id),
                ('med_id', '=', rec.med_id.id),
                ('batch_no', '=', rec.batch_no),
            ], limit=1)

            if inventory:
                inventory.write({
                    'qty_available': inventory.qty_available + rec.qty_in,
                    'supplier_id': rec.supplier_id.id,
                    'unit_price': rec.unit_price,  # ← تحديث السعر
                    'last_update': fields.Datetime.now(),
                })
            else:
                self.env['dawai.inventory'].create({
                    'pharm_id': rec.pharm_id.id,
                    'med_id': rec.med_id.id,
                    'supplier_id': rec.supplier_id.id,
                    'batch_no': rec.batch_no,
                    'qty_available': rec.qty_in,
                    'qty_reserved': 0,
                    'unit_price': rec.unit_price,  # ← السعر الجديد
                    'last_update': fields.Datetime.now(),
                })
            rec.state = 'done'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == 'done':
                raise ValidationError(
                    'لا يمكن إعادة الشحنة المعالجة للمسودة!'
                )
            rec.state = 'draft'

    @api.constrains('qty_in')
    def _check_qty(self):
        for rec in self:
            if rec.qty_in <= 0:
                raise ValidationError('الكمية يجب أن تكون أكبر من صفر!')
            if rec.qty_in > 10_000_000:
                raise ValidationError('الكمية تتجاوز الحد الأقصى (10,000,000)!')

    @api.constrains('unit_price')
    def _check_price(self):
        for rec in self:
            if rec.unit_price < 0:
                raise ValidationError('السعر لا يمكن أن يكون سالباً!')
