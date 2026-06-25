# -*- coding: utf-8 -*-
# ============================================================
# جدول 8: الوصفات الطبية (Prescriptions Table)
# الربط التسلسلي: يرجع لـ Booking(7)
#
# pat_id و med_id → related من booking_id (تسلسلي)
# ============================================================

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiPrescription(models.Model):
    _name = 'dawai.prescription'
    _description = 'جدول الوصفات الطبية'
    _rec_name = 'display_name'
    _order = 'issue_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── الربط التسلسلي: يرجع للحجز (7) ─────────────────
    booking_id = fields.Many2one(
        comodel_name='dawai.medicine.booking',
        string='رقم الحجز المرتبط',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 7 — يضمن وجود حجز نشط صحيح قبل تسجيل الوصفة',
    )

    # ─── Related من booking_id (الربط التسلسلي) ──────────
    pat_id = fields.Many2one(
        comodel_name='dawai.patient',
        related='booking_id.pat_id',
        string='المريض',
        store=True,
        readonly=True,
        help='مُستخرَج من الحجز — الجدول 4 عبر الجدول 7',
    )
    med_id = fields.Many2one(
        comodel_name='dawai.medicine',
        related='booking_id.med_id',
        string='الدواء',
        store=True,
        readonly=True,
        help='مُستخرَج من الحجز — الجدول 1 عبر الجداول 7→6',
    )
    pharm_id = fields.Many2one(
        comodel_name='dawai.pharmacy',
        related='booking_id.pharm_id',
        string='الصيدلية',
        store=True,
        readonly=True,
    )

    # ─── بيانات الوصفة ───────────────────────────────────
    doctor_name = fields.Char(
        string='اسم الطبيب',
        size=30,
        tracking=True,
    )
    doctor_phone = fields.Char(
        string='رقم هاتف الطبيب',
        size=15,
    )
    allowed_qty = fields.Integer(
        string='الكمية المسموحة شهرياً',
        required=True,
        tracking=True,
        help='الحد الأقصى الذي يمكن صرفه شهرياً بهذه الوصفة',
    )
    issue_date = fields.Date(
        string='تاريخ إصدار الوصفة',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    expiry_date = fields.Date(
        string='تاريخ انتهاء الوصفة',
        tracking=True,
    )
    qty_dispensed_so_far = fields.Integer(
        string='الكمية المصروفة حتى الآن',
        default=0,
        readonly=True,
        tracking=True,
        help='يُحدَّث تلقائياً عند كل عملية صرف',
    )

    # ─── Computed ─────────────────────────────────────────
    qty_remaining = fields.Integer(
        string='الكمية المتبقية',
        compute='_compute_qty_remaining',
        store=True,
    )
    is_valid = fields.Boolean(
        string='الوصفة سارية؟',
        compute='_compute_is_valid',
        store=True,
    )
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('allowed_qty', 'qty_dispensed_so_far')
    def _compute_qty_remaining(self):
        for rec in self:
            rec.qty_remaining = max(
                rec.allowed_qty - rec.qty_dispensed_so_far, 0
            )

    @api.depends('expiry_date', 'qty_dispensed_so_far', 'allowed_qty')
    def _compute_is_valid(self):
        today = fields.Date.today()
        for rec in self:
            not_expired = (not rec.expiry_date or rec.expiry_date >= today)
            has_remaining = rec.qty_remaining > 0
            rec.is_valid = not_expired and has_remaining

    @api.depends('booking_id', 'issue_date')
    def _compute_display_name(self):
        for rec in self:
            pat  = rec.pat_id.pat_name   if rec.pat_id  else '—'
            med  = rec.med_id.med_name   if rec.med_id  else '—'
            date = str(rec.issue_date)   if rec.issue_date else '—'
            rec.display_name = f'وصفة: {pat} | {med} | {date}'

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('allowed_qty')
    def _check_allowed_qty(self):
        for rec in self:
            if rec.allowed_qty <= 0:
                raise ValidationError(
                    'الكمية المسموحة يجب أن تكون أكبر من صفر!'
                )

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.expiry_date and rec.issue_date:
                if rec.expiry_date < rec.issue_date:
                    raise ValidationError(
                        'تاريخ انتهاء الوصفة لا يمكن أن يكون قبل تاريخ الإصدار!'
                    )

    @api.constrains('qty_dispensed_so_far', 'allowed_qty')
    def _check_dispensed_not_exceed(self):
        for rec in self:
            if rec.qty_dispensed_so_far > rec.allowed_qty:
                raise ValidationError(
                    f'الكمية المصروفة ({rec.qty_dispensed_so_far}) '
                    f'تجاوزت الكمية المسموحة ({rec.allowed_qty})!'
                )
