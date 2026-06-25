# -*- coding: utf-8 -*-
# ============================================================
# جدول 7: حجز الأدوية (Medicine Booking Table) - النسخة النهائية المدمجة
# الربط التسلسلي: يرجع لـ Inventory(6) + Patient(4)
# ============================================================

import random
import string
from datetime import timedelta

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiMedicineBooking(models.Model):
    _name = 'dawai.medicine.booking'
    _description = 'جدول حجز الأدوية'
    _rec_name = 'booking_code'
    _order = 'booking_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── حقول الربط التسلسلي ─────────────────────────────
    pat_id = fields.Many2one(
        comodel_name='dawai.patient',
        string='المريض',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 4 — المريض الذي قام بالحجز',
    )
    stock_id = fields.Many2one(
        comodel_name='dawai.inventory',
        string='سجل المخزون',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='الجدول 6 — يضمن أن الدواء متوفر في تلك الصيدلية تحديداً',
    )

    # ─── Related من stock_id (الربط التسلسلي بدون تكرار) ──
    med_id = fields.Many2one(
        comodel_name='dawai.medicine',
        related='stock_id.med_id',
        string='الدواء',
        store=True,
        readonly=True,
        help='مُستخرَج تلقائياً من سجل المخزون',
    )
    pharm_id = fields.Many2one(
        comodel_name='dawai.pharmacy',
        related='stock_id.pharm_id',
        string='الصيدلية',
        store=True,
        readonly=True,
        help='مُستخرَج تلقائياً من سجل المخزون',
    )

    # ─── بيانات الكمية والسعر (تم تعديل السعر ليكون ثابتاً) ──
    qty_booked = fields.Integer(
        string='الكمية المطلوبة',
        required=True,
        default=1,
        tracking=True,
        help='الكمية التي يريد المريض حجزها — تُحجز من qty_reserved',
    )
    unit_price_at_booking = fields.Float(
        string='السعر وقت الحجز (SDG)',
        store=True,
        readonly=True,
        tracking=True,
        help='يُحفظ كقيمة ثابتة وقت الحجز ولا يتأثر بتغير سعر المخزون لاحقاً',
    )
    total_price = fields.Float(
        string='الإجمالي (SDG)',
        compute='_compute_total_price',
        store=True,
    )

    # ─── بيانات الحجز ────────────────────────────────────
    booking_date = fields.Datetime(
        string='زمن إنشاء الحجز',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
    )
    pickup_deadline = fields.Datetime(
        string='موعد انتهاء الحجز (24 ساعة)',
        compute='_compute_pickup_deadline',
        store=True,
        readonly=True,
        help='يُحسب تلقائياً = booking_date + 24 ساعة',
    )
    status = fields.Selection(
        selection=[
            ('active', 'مؤكد / نشط'),
            ('dispensed', 'تم الصرف'),
            ('cancelled', 'ملغي'),
            ('expired', 'منتهي المدة'),
        ],
        string='حالة الحجز',
        default='active',
        required=True,
        tracking=True,
    )
    booking_code = fields.Char(
        string='رمز الحجز',
        size=10,
        readonly=True,
        copy=False,
        tracking=True,
        help='يظهره المريض للصيدلاني عند الاستلام',
    )
    verification_code = fields.Char(
        string='رمز التحقق',
        size=10,
        readonly=True,
        copy=False,
        help='يُولَّد عشوائياً من النظام — للتحقق المزدوج',
    )

    # ─── Computed: معلومات مساعدة ────────────────────────
    is_expired = fields.Boolean(
        string='منتهي؟',
        compute='_compute_is_expired',
        store=False,
    )
    requires_prescription = fields.Boolean(
        related='med_id.requires_prescription',
        string='يحتاج وصفة؟',
        readonly=True,
    )

    # ─── Onchange Methods (واجهة المستخدم) ────────────────
    @api.onchange('stock_id')
    def _onchange_stock_id(self):
        """تعبئة السعر تلقائياً في واجهة المستخدم بمجرد اختيار المخزون"""
        if self.stock_id:
            self.unit_price_at_booking = self.stock_id.unit_price
        else:
            self.unit_price_at_booking = 0.0

    # ─── Compute Methods ──────────────────────────────────
    @api.depends('unit_price_at_booking', 'qty_booked')
    def _compute_total_price(self):
        for rec in self:
            rec.total_price = rec.unit_price_at_booking * rec.qty_booked

    @api.depends('booking_date')
    def _compute_pickup_deadline(self):
        for rec in self:
            if rec.booking_date:
                rec.pickup_deadline = rec.booking_date + timedelta(hours=24)
            else:
                rec.pickup_deadline = False

    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_expired = (
                    rec.status == 'active' and
                    rec.pickup_deadline and
                    rec.pickup_deadline < now
            )

    # ─── توليد الكودات ────────────────────────────────────
    @staticmethod
    def _generate_code(length=10):
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choices(chars, k=length))

    # ─── Create: تجميد السعر + توليد الكودات + حجز الكمية ─
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['booking_code'] = self._generate_code()
            vals['verification_code'] = self._generate_code()

            # ضمان تجميد السعر في قاعدة البيانات حتى لو لم يُمرر من الواجهة
            if 'stock_id' in vals and not vals.get('unit_price_at_booking'):
                stock_record = self.env['dawai.inventory'].browse(vals['stock_id'])
                vals['unit_price_at_booking'] = stock_record.unit_price

        records = super().create(vals_list)

        # حجز الكمية في المخزون فور إنشاء الحجز
        for rec in records:
            rec.stock_id.write({
                'qty_reserved': rec.stock_id.qty_reserved + rec.qty_booked,
                'last_update': fields.Datetime.now(),
            })
        return records

    # ─── إلغاء الحجز: استعادة الكمية المحجوزة ────────────
    def action_cancel(self):
        for rec in self:
            if rec.status not in ('active',):
                raise ValidationError(
                    f'لا يمكن إلغاء حجز بحالة "{rec.status}"!'
                )
            rec.stock_id.write({
                'qty_reserved': max(
                    rec.stock_id.qty_reserved - rec.qty_booked, 0
                ),
                'last_update': fields.Datetime.now(),
            })
            rec.status = 'cancelled'

    # ─── Cron: انتهاء صلاحية الحجوزات بعد 24 ساعة ────────
    @api.model
    def _cron_expire_bookings(self):
        """يُشغَّل كل فترة — يُحوّل الحجوزات المنتهية لـ expired"""
        expired = self.search([
            ('status', '=', 'active'),
            ('pickup_deadline', '<', fields.Datetime.now()),
        ])
        for rec in expired:
            rec.stock_id.write({
                'qty_reserved': max(
                    rec.stock_id.qty_reserved - rec.qty_booked, 0
                ),
                'last_update': fields.Datetime.now(),
            })
        expired.write({'status': 'expired'})

    # ─── Python Constraints ───────────────────────────────
    @api.constrains('qty_booked', 'stock_id')
    def _check_qty_availability(self):
        for rec in self:
            if rec.qty_booked <= 0:
                raise ValidationError('الكمية يجب أن تكون أكبر من صفر!')
            net = rec.stock_id.qty_available - rec.stock_id.qty_reserved
            if rec.qty_booked > net:
                raise ValidationError(
                    f'الكمية المطلوبة ({rec.qty_booked}) '
                    f'تتجاوز المتاح للحجز ({net})!'
                )

    @api.constrains('pat_id', 'med_id', 'status')
    def _check_unique_active_booking(self):
        """
        Python Constraint:
        UNIQUE(pat_id, med_id) WHERE status = 'active'
        لمنع تكرار الحجز النشط لنفس الدواء من نفس المريض
        """
        for rec in self:
            if rec.status == 'active':
                duplicate = self.search([
                    ('pat_id', '=', rec.pat_id.id),
                    ('med_id', '=', rec.med_id.id),
                    ('status', '=', 'active'),
                    ('id', '!=', rec.id),
                ])
                if duplicate:
                    raise ValidationError(
                        f'المريض "{rec.pat_id.pat_name}" لديه حجز نشط بالفعل '
                        f'لدواء "{rec.med_id.med_name}"!\n'
                        f'رمز الحجز الحالي: {duplicate[0].booking_code}'
                    )

    @api.constrains('qty_booked')
    def _check_qty_positive(self):
        for rec in self:
            if rec.qty_booked <= 0:
                raise ValidationError('الكمية المحجوزة يجب أن تكون أكبر من صفر!')

    # ─── زر الصرف السريع من داخل شاشة الحجز ──────────────
    def action_open_dispense(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'تأكيد صرف الدواء',
            'res_model': 'dawai.dispensing.transaction',
            'view_mode': 'form',
            # نمرر بيانات الحجز الحالية لتُكتب تلقائياً في شاشة الصرف الجديدة
            'context': {
                'default_booking_id': self.id,
                'default_qty_dispensed': self.qty_booked,
                'default_unit_price': self.unit_price_at_booking,
            },
            'target': 'new',  # يفتحها في نافذة منبثقة (Pop-up) للسرعة
        }