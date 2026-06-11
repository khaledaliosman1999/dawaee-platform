# -*- coding: utf-8 -*-
# ============================================================
# جدول 9: عمليات الصرف (Dispensing Transactions)
# "الجدول الدوري" — يوثق الحركة الفعلية ويمنع التلاعب
# الربط التسلسلي: يرجع لـ Booking(7) + Prescription(8)
#
# - med_id, pharm_id → related من booking_id (تسلسلي بدون تكرار)
# - presc_id → nullable (أدوية بدون وصفة)
# - عند الإنشاء: يُحدِّث المخزون + حالة الحجز + الوصفة تلقائياً
# ============================================================

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiDispensingTransaction(models.Model):
    _name = 'dawai.dispensing.transaction'
    _description = 'جدول عمليات الصرف'
    _rec_name = 'display_name'
    _order = 'dispense_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── الربط التسلسلي الأساسي: يرجع للحجز (7) ──────────
    booking_id = fields.Many2one(
        comodel_name='dawai.medicine.booking',
        string='رقم الحجز',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 7 — يضمن: مريض + دواء + صيدلية + حجز صحيح',
    )

    # ─── Related من booking_id (الربط التسلسلي بدون تكرار)
    med_id = fields.Many2one(
        comodel_name='dawai.medicine',
        related='booking_id.med_id',
        string='الدواء',
        store=True,
        readonly=True,
        help='مُستخرَج من الحجز → المخزون → الدواء',
    )
    pharm_id = fields.Many2one(
        comodel_name='dawai.pharmacy',
        related='booking_id.pharm_id',
        string='الصيدلية',
        store=True,
        readonly=True,
        help='مُستخرَج من الحجز → المخزون → الصيدلية',
    )
    pat_id = fields.Many2one(
        comodel_name='dawai.patient',
        related='booking_id.pat_id',
        string='المريض',
        store=True,
        readonly=True,
    )

    # ─── الربط التسلسلي الثانوي: يرجع للوصفة (8) ─────────
    # nullable: أدوية لا تحتاج وصفة (requires_prescription = False)
    presc_id = fields.Many2one(
        comodel_name='dawai.prescription',
        string='الوصفة المستخدمة',
        ondelete='restrict',
        required=False,
        tracking=True,
        help='الجدول 8 — اختياري: مطلوب فقط للأدوية التي تحتاج وصفة',
    )

    # ─── بيانات عملية الصرف ──────────────────────────────
    qty_dispensed = fields.Integer(
        string='الكمية التي صُرفت فعلياً',
        required=True,
        tracking=True,
    )
    dispense_date = fields.Datetime(
        string='التاريخ والوقت بدقة',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
    )
    unit_price = fields.Float(
        string='سعر الوحدة (SDG)',
        digits=(10, 2),
        tracking=True,
    )
    total_price = fields.Float(
        string='الإجمالي (SDG)',
        compute='_compute_total_price',
        store=True,
    )

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    # ─── Compute Methods ──────────────────────────────────
    @api.depends('qty_dispensed', 'unit_price')
    def _compute_total_price(self):
        for rec in self:
            rec.total_price = rec.qty_dispensed * rec.unit_price

    @api.depends('booking_id', 'dispense_date')
    def _compute_display_name(self):
        for rec in self:
            code = rec.booking_id.booking_code if rec.booking_id else '—'
            date = str(rec.dispense_date)[:16]  if rec.dispense_date else '—'
            rec.display_name = f'صرف [{code}] — {date}'

    # ─── Create: تحديث تسلسلي للجداول السابقة ────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # 1. تحديث حالة الحجز (7) → dispensed
            rec.booking_id.write({'status': 'dispensed'})

            # 2. تحديث المخزون (6) — تخفيض الكميات
            stock = rec.booking_id.stock_id
            new_available = stock.qty_available - rec.qty_dispensed
            new_reserved  = max(
                stock.qty_reserved - rec.booking_id.qty_booked, 0
            )
            if new_available < 0:
                raise ValidationError(
                    f'خطأ: الكمية المصروفة ({rec.qty_dispensed}) '
                    f'تتجاوز المتاحة في المخزون ({stock.qty_available})!'
                )
            stock.write({
                'qty_available': new_available,
                'qty_reserved':  new_reserved,
                'last_update':   fields.Datetime.now(),
            })

            # 3. تحديث الوصفة (8) — إن وجدت
            if rec.presc_id:
                new_dispensed = (
                    rec.presc_id.qty_dispensed_so_far + rec.qty_dispensed
                )
                if new_dispensed > rec.presc_id.allowed_qty:
                    raise ValidationError(
                        f'الكمية المصروفة تتجاوز المسموح به في الوصفة '
                        f'({rec.presc_id.allowed_qty})!'
                    )
                rec.presc_id.write({
                    'qty_dispensed_so_far': new_dispensed
                })
        return records

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('qty_dispensed')
    def _check_qty(self):
        for rec in self:
            if rec.qty_dispensed <= 0:
                raise ValidationError(
                    'الكمية المصروفة يجب أن تكون أكبر من صفر!'
                )

    @api.constrains('booking_id')
    def _check_booking_status(self):
        for rec in self:
            if rec.booking_id.status != 'active':
                raise ValidationError(
                    f'لا يمكن الصرف على حجز بحالة '
                    f'"{rec.booking_id.status}"!\n'
                    f'يجب أن يكون الحجز بحالة "مؤكد / نشط".'
                )
            now = fields.Datetime.now()
            if rec.booking_id.pickup_deadline < now:
                raise ValidationError(
                    'انتهت مهلة الحجز (24 ساعة)!\n'
                    'لا يمكن الصرف على حجز منتهي المدة.'
                )

    @api.constrains('presc_id', 'booking_id')
    def _check_prescription_required(self):
        """إن كان الدواء يحتاج وصفة — يجب ربط وصفة"""
        for rec in self:
            if (rec.med_id and
                    rec.med_id.requires_prescription and
                    not rec.presc_id):
                raise ValidationError(
                    f'الدواء "{rec.med_id.med_name}" يحتاج وصفة طبية!\n'
                    f'يرجى ربط الوصفة الطبية قبل إتمام الصرف.'
                )
