# -*- coding: utf-8 -*-
# ============================================================
# جدول 4: المرضى (Patients Table)
# يمثل كينونة المستفيد
#
# ملاحظة التصميم:
# - النظام يعمل كمنصة: التصفح والبحث بدون تسجيل دخول
# - عند الضغط على "احجز" يُطلب من الزائر تسجيل الدخول
# - user_id يُملأ عند إنشاء الحساب ويبقى ثابتاً (nullable)
# ============================================================

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiPatient(models.Model):
    _name = 'dawai.patient'
    _description = 'جدول المرضى'
    _rec_name = 'pat_name'
    _order = 'pat_name asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── الحقول الأساسية ─────────────────────────────────
    pat_name = fields.Char(
        string='الاسم الكامل',
        size=60,        # تعديل: 30 → 60 (الأسماء الرباعية عربياً)
        required=True,
        tracking=True,
    )
    national_id = fields.Char(
        string='الرقم الوطني',
        size=11,
        tracking=True,
        help='الرقم الوطني السوداني (11 رقم)',
    )
    disease_type = fields.Selection(
        selection=[
            ('diabetes',   'سكري'),
            ('pressure',   'ضغط دم'),
            ('heart',      'قلب'),
            ('asthma',     'ربو'),
            ('other',      'أخرى'),
        ],
        string='نوع المرض',
        tracking=True,
        help='التصنيف الرئيسي — يتوافق مع فئات الأدوية المستهدفة',
    )
    contact_info = fields.Char(
        string='رقم الهاتف الأساسي',
        size=15,
    )
    email = fields.Char(
        string='البريد الإلكتروني',
        size=60,        # تعديل: 30 → 60 (البريد قد يتجاوز 30 حرفاً)
    )
    active = fields.Boolean(
        string='حالة الحساب',
        default=True,
        tracking=True,
        help='للأرشفة في Odoo',
    )

    # ─── تعديل مقترح: ربط بحساب Odoo ────────────────────
    # nullable: يُملأ فقط عندما يسجل المريض حسابه عبر المنصة
    # - المريض يتصفح بدون حساب ← user_id = False
    # - يضغط "احجز" ← يسجل دخولاً / يُنشئ حساباً ← user_id يُملأ
    # - بدونه: النظام لا يعرف أي Patient record يخص المستخدم المُسجَّل
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='حساب المريض (Portal)',
        ondelete='restrict',
        copy=False,
        tracking=True,
        help='يُربط تلقائياً عند تسجيل المريض عبر المنصة. لا يتغير بعد الربط.',
    )

    # ─── Computed ─────────────────────────────────────────
    booking_count = fields.Integer(
        string='عدد الحجوزات',
        compute='_compute_booking_count',
    )
    active_booking_count = fields.Integer(
        string='الحجوزات النشطة',
        compute='_compute_booking_count',
    )

    def _compute_booking_count(self):
        for rec in self:
            all_bookings = self.env['dawai.medicine.booking'].search([
                ('pat_id', '=', rec.id)
            ])
            rec.booking_count = len(all_bookings)
            rec.active_booking_count = len(
                all_bookings.filtered(lambda b: b.status == 'active')
            )

    # ─── Smart Button ─────────────────────────────────────
    def action_view_bookings(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'حجوزات {self.pat_name}',
            'res_model': 'dawai.medicine.booking',
            'view_mode': 'list,form',
            'domain': [('pat_id', '=', self.id)],
            'context': {'default_pat_id': self.id},
        }

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('national_id')
    def _check_national_id(self):
        for rec in self:
            if rec.national_id and not rec.national_id.isdigit():
                raise ValidationError('الرقم الوطني يجب أن يحتوي على أرقام فقط!')
            if rec.national_id and len(rec.national_id) != 12:
                raise ValidationError('الرقم الوطني يجب أن يكون 12 رقماً بالضبط!')

    @api.constrains('email')
    def _check_email(self):
        for rec in self:
            if rec.email and '@' not in rec.email:
                raise ValidationError('صيغة البريد الإلكتروني غير صحيحة!')

    # ─── SQL Constraints ──────────────────────────────────
    _sql_constraints = [
        ('national_id_unique',
         'UNIQUE(national_id)',
         'الرقم الوطني مستخدم بالفعل!'),
        ('user_id_unique',
         'UNIQUE(user_id)',
         'هذا الحساب مرتبط بمريض آخر بالفعل!'),
    ]
