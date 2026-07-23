# ============================================================
# جدول 3: الصيدليات (Pharmacies Table)
# يمثل كينونة الجهة الموفرة للخدمة
# ============================================================

import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DawaiPharmacy(models.Model):
    _name = 'dawai.pharmacy'
    _description = 'جدول الصيدليات'
    _rec_name = 'pharm_name'
    _order = 'pharm_name asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── الحقول الأساسية ─────────────────────────────────
    pharm_name = fields.Char(
        string='اسم الصيدلية',
        size=50,
        required=True,
        tracking=True,
    )
    license_no = fields.Char(
        string='رقم الترخيص',
        size=30,
        required=True,
        tracking=True,
        help='رقم ترخيص الصيدلية الصادر من وزارة الصحة',
    )
    # ربط بنظام Odoo — حساب المسؤول عن الصيدلية
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='حساب المسؤول (مسؤول الصيدلية)',
        ondelete='restrict',
        tracking=True,
        help='يُربط بحساب Odoo الخاص بمسؤول الصيدلية لتسجيل الدخول',
    )
    pharmacy_phone = fields.Char(
        string='رقم التواصل',
        size=20,
    )
    address = fields.Text(
        string='العنوان',
        required=True,
    )

    map_url = fields.Char(
        string='رابط الخريطة (Google Maps)',
        size=200,
        required=True,
        help='رابط إحداثيات الصيدلية على خريطة Google',
    )
    active = fields.Boolean(
        string='حالة الصيدلية في النظام',
        default=True,
        required=True,
        tracking=True,
        help='إلغاء التحديد = أرشفة الصيدلية في Odoo',
    )

    # ─── Computed ─────────────────────────────────────────
    inventory_count = fields.Integer(
        string='عدد الأدوية في المخزون',
        compute='_compute_counts',
    )
    booking_count = fields.Integer(
        string='عدد الحجوزات النشطة',
        compute='_compute_counts',
    )

    def _compute_counts(self):
        for rec in self:
            rec.inventory_count = self.env['dawai.inventory'].search_count([
                ('pharm_id', '=', rec.id), ('active', '=', True)
            ])
            rec.booking_count = self.env['dawai.medicine.booking'].search_count([
                ('pharm_id', '=', rec.id), ('status', '=', 'active')
            ])

    # ─── Smart Buttons ────────────────────────────────────
    def action_view_inventory(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'مخزون {self.pharm_name}',
            'res_model': 'dawai.inventory',
            'view_mode': 'list,form',
            'domain': [('pharm_id', '=', self.id)],
            'context': {'default_pharm_id': self.id},
        }

    def action_view_bookings(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'حجوزات {self.pharm_name}',
            'res_model': 'dawai.medicine.booking',
            'view_mode': 'list,form',
            'domain': [('pharm_id', '=', self.id)],
            'context': {'default_pharm_id': self.id},
        }

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('pharmacy_phone')
    def _check_phone(self):
        phone_regex = r'^\+?\d{9,15}$'
        for rec in self:
            if rec.pharmacy_phone and not re.match(phone_regex, rec.pharmacy_phone):
                raise ValidationError('رقم هاتف الصيدلية يجب أن يتكون من أرقام فقط وبطول صحيح.')

    @api.constrains('map_url')
    def _check_map_url(self):
        for rec in self:
            if rec.map_url and not rec.map_url.startswith(('http://', 'https://')):
                raise ValidationError('رابط خريطة Google يجب أن يكون رابطاً صحيحاً يبدأ بـ http:// أو https://')

    # ─── SQL Constraints ──────────────────────────────────
    _sql_constraints = [
        ('license_no_unique',
         'UNIQUE(license_no)',
         'رقم الترخيص مستخدم بالفعل لصيدلية أخرى!'),
        ('map_url_unique',
         'UNIQUE(map_url)',
         'رابط الخريطة مستخدم بالفعل!'),
        ('user_id_unique',
         'UNIQUE(user_id)',
         'هذا الحساب مرتبط بصيدلية أخرى بالفعل!'),
    ]
