# -*- coding: utf-8 -*-
# ============================================================
# جدول 8: الوصفات الطبية (Prescriptions Table)
# التعديل الجديد: الوصفة مستقلة، تُربط بمريض واحد، وتحتوي عدة أدوية
# ملاحظة هامة: يتم التعامل مع الوصفة بنظام "مرات الصرف" (Refills)
# ============================================================

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiPrescription(models.Model):
    _name = 'dawai.prescription'
    _description = 'جدول الوصفات الطبية'
    _rec_name = 'display_name'
    _order = 'issue_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── الربط المباشر بالمريض (بدلاً من الحجز) ───────────
    pat_id = fields.Many2one(
        comodel_name='dawai.patient',
        string='المريض',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 4 — المريض صاحب الوصفة',
    )

    # ─── علاقة متعدد إلى متعدد (عدة أدوية في وصفة واحدة) ──
    medicine_ids = fields.Many2many(
        comodel_name='dawai.medicine',
        string='الأدوية الموصوفة',
        required=True,
        help='الجدول 1 — يمكن اختيار دواء واحد أو أكثر في نفس الوصفة',
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

    # ─── إحصائيات مرات الصرف (Refills) ───────────────────
    allowed_qty = fields.Integer(
        string='إجمالي مرات الصرف المسموحة',
        required=True,
        default=1,
        tracking=True,
        help='الحد الأقصى لعدد المرات التي يمكن للمريض فيها صرف أدوية هذه الوصفة',
    )
    qty_dispensed_so_far = fields.Integer(
        string='مرات الصرف الفعلية',
        default=0,
        readonly=True,
        tracking=True,
        help='يُحدَّث تلقائياً بزيادة (1) عند كل عملية صرف مرتبطة بهذه الوصفة',
    )

    # ─── التواريخ ─────────────────────────────────────────
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

    # ─── Computed ─────────────────────────────────────────
    qty_remaining = fields.Integer(
        string='المرات المتبقية',
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

    @api.depends('pat_id', 'issue_date')
    def _compute_display_name(self):
        for rec in self:
            pat = rec.pat_id.pat_name if rec.pat_id else '—'
            date = str(rec.issue_date) if rec.issue_date else '—'
            rec.display_name = f'وصفة: {pat} | {date}'

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('allowed_qty')
    def _check_allowed_qty(self):
        for rec in self:
            if rec.allowed_qty <= 0:
                raise ValidationError(
                    'مرات الصرف المسموحة يجب أن تكون أكبر من صفر!'
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
                    f'مرات الصرف الفعلية ({rec.qty_dispensed_so_far}) '
                    f'تجاوزت المسموح به ({rec.allowed_qty})!'
                )