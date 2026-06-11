# -*- coding: utf-8 -*-
# ============================================================
# جدول 6: المخزون (Inventory / Stock Table)
# يربط الأدوية بالصيدليات ويحدد الكميات المتوفرة لحظياً
#
# الربط التسلسلي:
# - يُنشأ / يُحدَّث عبر StockInbound(5) فقط (action_confirm)
# - الجداول اللاحقة (7+) تستعلم منه عن الكميات
#
# القيد المركب:
# UNIQUE(pharm_id, med_id, batch_no) — لمنع تكرار نفس الدواء
# ============================================================

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiInventory(models.Model):
    _name = 'dawai.inventory'
    _description = 'جدول المخزون'
    _rec_name = 'display_name'
    _order = 'pharm_id, med_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── حقول الربط (FK — القيد المركب عليها) ────────────
    pharm_id = fields.Many2one(
        comodel_name='dawai.pharmacy',
        string='الصيدلية',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 3 — مُملَّأ من StockInbound(5)',
    )
    med_id = fields.Many2one(
        comodel_name='dawai.medicine',
        string='الدواء',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 1 — مُملَّأ من StockInbound(5)',
    )
    supplier_id = fields.Many2one(
        comodel_name='dawai.supplier',
        string='المورد',
        ondelete='restrict',
        tracking=True,
        help='آخر مورد وفّر هذا الدواء',
    )
    batch_no = fields.Char(
        string='رقم الدفعة',
        size=20,
        tracking=True,
        help='جزء من القيد المركب UNIQUE(pharm_id, med_id, batch_no)',
    )
    unit_price = fields.Float(
        string='سعر الوحدة في هذه الصيدلية (SDG)',
        digits=(10, 2),
        default=0.0,
        help='السعر الفعلي الذي تبيعه هذه الصيدلية — يختلف من صيدلية لأخرى',
    )

    # ─── بيانات الكميات ──────────────────────────────────
    qty_available = fields.Integer(
        string='الكمية الفعلية على الرف',
        default=0,
        tracking=True,
    )
    qty_reserved = fields.Integer(
        string='الكمية المحجوزة (لم تُصرف)',
        default=0,
        tracking=True,
    )
    qty_net = fields.Integer(
        string='الكمية المتاحة للحجز',
        compute='_compute_qty_net',
        store=True,
        help='qty_available − qty_reserved',
    )
    last_update = fields.Datetime(
        string='تاريخ آخر تحديث',
        readonly=True,
    )
    expiry_date = fields.Datetime(
        string='تاريخ انتهاء الصلاحية',
        tracking=True,
    )
    min_stock_level = fields.Integer(
        string='الحد الأدنى للتنبيه',
        default=5,
        tracking=True,
        help='يرسل تنبيهاً عند وصول الكمية لهذا الحد',
    )
    active = fields.Boolean(
        string='حالة السجل',
        default=True,
        tracking=True,
        help='للأرشفة أو الحذف الآمن في Odoo',
    )

    # ─── حقل محسوب: تنبيه انخفاض المخزون ───────────────
    is_low_stock = fields.Boolean(
        string='مخزون منخفض؟',
        compute='_compute_low_stock',
        store=True,
    )

    # ─── Display Name ─────────────────────────────────────
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('med_id', 'pharm_id', 'batch_no')
    def _compute_display_name(self):
        for rec in self:
            med = rec.med_id.med_name if rec.med_id else '—'
            phm = rec.pharm_id.pharm_name if rec.pharm_id else '—'
            bat = f'[{rec.batch_no}]' if rec.batch_no else ''
            rec.display_name = f'{med} @ {phm} {bat}'

    @api.depends('qty_available', 'qty_reserved')
    def _compute_qty_net(self):
        for rec in self:
            rec.qty_net = max(rec.qty_available - rec.qty_reserved, 0)

    @api.depends('qty_available', 'min_stock_level')
    def _compute_low_stock(self):
        for rec in self:
            rec.is_low_stock = (
                    rec.qty_available > 0 and
                    rec.qty_available <= rec.min_stock_level
            )

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('qty_available', 'qty_reserved')
    def _check_quantities(self):
        for rec in self:
            if rec.qty_available < 0:
                raise ValidationError('الكمية المتاحة لا يمكن أن تكون سالبة!')
            if rec.qty_reserved < 0:
                raise ValidationError('الكمية المحجوزة لا يمكن أن تكون سالبة!')
            if rec.qty_reserved > rec.qty_available:
                raise ValidationError(
                    f'الكمية المحجوزة ({rec.qty_reserved}) '
                    f'تتجاوز الكمية المتاحة ({rec.qty_available})!'
                )

    # ─── القيد المركب ─────────────────────────────────────
    _sql_constraints = [
        ('stock_unique',
         'UNIQUE(pharm_id, med_id, batch_no)',
         'هذا الدواء بنفس رقم الدفعة موجود بالفعل في هذه الصيدلية!'),
    ]
