# -*- coding: utf-8 -*-
# ============================================================
# جدول 5: توريد المخزن (Stock Inbound)
# يربط المورد(2) بالصيدلية(3) والدواء(1)
# بدونه لن تزيد الكميات في النظام
#
# الربط التسلسلي: يرجع مباشرة للجداول الأساسية 1+2+3
# الجداول اللاحقة (6+) ترجع لهذا الجدول ضمنياً عبر Inventory
# ============================================================

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiStockInbound(models.Model):
    _name = 'dawai.stock.inbound'
    _description = 'جدول توريد المخزن'
    _rec_name = 'display_name'
    _order = 'in_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── حقول الربط (FK — يشكّلان معاً Composite Key) ────
    supplier_id = fields.Many2one(
        comodel_name='dawai.supplier',
        string='المورد',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 2 — المورد الذي أرسل الشحنة',
    )
    pharm_id = fields.Many2one(
        comodel_name='dawai.pharmacy',
        string='الصيدلية المستلِمة',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 3 — الصيدلية التي استلمت الشحنة',
    )
    med_id = fields.Many2one(
        comodel_name='dawai.medicine',
        string='الدواء',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 1 — الدواء الوارد في الشحنة',
    )

    # ─── بيانات الشحنة ───────────────────────────────────
    qty_in = fields.Integer(
        string='الكمية التي دخلت المخزن',
        required=True,
        tracking=True,
        help='الحد الأقصى: 10,000,000 وحدة',
    )
    in_date = fields.Date(
        string='تاريخ دخول الشحنة',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    batch_no = fields.Char(
        string='رقم الدفعة',
        size=20,
        tracking=True,
        help='لتتبع الدفعات وتواريخ الصلاحية',
    )
    unit_price = fields.Float(
        string='سعر الوحدة (SDG)',
        digits=(10, 2),
        default=0.0,
        help='سعر البيع في هذه الصيدلية',
    )

    # حالة المعالجة
    state = fields.Selection(
        selection=[
            ('draft', 'مسودة'),
            ('confirmed', 'مؤكدة'),
            ('done', 'مُعالَجة — تم تحديث المخزون'),
        ],
        string='الحالة',
        default='draft',
        tracking=True,
        readonly=True,
    )

    # ─── Display Name ─────────────────────────────────────
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('med_id', 'pharm_id', 'in_date')
    def _compute_display_name(self):
        for rec in self:
            med = rec.med_id.med_name if rec.med_id else '—'
            phm = rec.pharm_id.pharm_name if rec.pharm_id else '—'
            date = str(rec.in_date) if rec.in_date else '—'
            rec.display_name = f'[{date}] {med} ← {phm}'

    # ─── Action: تحديث المخزون ────────────────────────────
    def action_confirm_and_update_inventory(self):
        """
        عند تأكيد الشحنة:
        - إن وجد سجل Inventory لنفس (pharm+med+batch) → qty_available +=
        - إن لم يوجد → ينشئ سجل Inventory جديد
        هذا هو الربط التسلسلي: StockInbound(5) → Inventory(6)
        """
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
                    'لا يمكن إعادة الشحنة المعالجة للمسودة — '
                    'يرجى تصحيح المخزون يدوياً إن لزم الأمر.'
                )
            rec.state = 'draft'

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('qty_in')
    def _check_qty(self):
        for rec in self:
            if rec.qty_in <= 0:
                raise ValidationError('الكمية يجب أن تكون أكبر من صفر!')
            if rec.qty_in > 10_000_000:
                raise ValidationError('الكمية تتجاوز الحد الأقصى المسموح (10,000,000)!')
