# ============================================================
# جدول 2: الموردين (Suppliers Table)
# لتوثيق مصادر الأدوية (شركات الأدوية أو الإمدادات الطبية)
# ============================================================
import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DawaiSupplier(models.Model):
    _name = 'dawai.supplier'
    _description = 'جدول الموردين'
    _rec_name = 'supplier_name'
    _order = 'supplier_name asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── الحقول الأساسية ─────────────────────────────────
    supplier_name = fields.Char(
        string='اسم الشركة / الجهة',
        size=60,
        required=True,
        tracking=True,
    )
    supplier_type = fields.Selection(
        selection=[
            ('government',    'حكومي'),
            ('private',       'خاص'),
            ('international', 'دولي'),
        ],
        string='نوع المورد',
        tracking=True,
    )
    contact_name = fields.Char(
        string='الشخص المسؤول للتواصل',
        size=30,
    )
    phone = fields.Char(
        string='رقم الهاتف',
        size=20,
    )

    email = fields.Char(
        string='البريد الإلكتروني',
        size=60,
    )
    address = fields.Text(
        string='العنوان',
    )
    active = fields.Boolean(
        string='نشط',
        default=True,
        tracking=True,
    )

    # ─── Computed ─────────────────────────────────────────
    inbound_count = fields.Integer(
        string='عدد الشحنات',
        compute='_compute_inbound_count',
    )

    def _compute_inbound_count(self):
        for rec in self:
            rec.inbound_count = self.env['dawai.stock.inbound'].search_count([
                ('supplier_id', '=', rec.id)
            ])

    def action_view_inbound(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'شحنات {self.supplier_name}',
            'res_model': 'dawai.stock.inbound',
            'view_mode': 'list,form',
            'domain': [('supplier_id', '=', self.id)],
            'context': {'default_supplier_id': self.id},
        }

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('email')
    def _check_email(self):
        # تعريف التعبير النمطي للبريد الإلكتروني القياسي
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

        for rec in self:
            if rec.email:  # نتحقق فقط إذا كان الحقل غير فارغ
                # استخدام re.match للتحقق من تطابق النص مع النمط
                if not re.match(email_regex, rec.email):
                    raise ValidationError(
                        'صيغة البريد الإلكتروني غير صحيحة! يرجى التأكد من كتابته بدون مسافات وبصيغة سليمة (مثال: info@company.com).')

    @api.constrains('phone')
    def _check_phone(self):
        """
        التحقق من أن رقم الهاتف يحتوي على أرقام فقط (ويمكن أن يبدأ بـ +).
        ويمكنك تعديل {9,15} لتناسب عدد أرقام هواتف محدد (مثلاً {11,11} إذا كان حصراً 11 رقم).
        """
        phone_regex = r'^\+?\d{9,15}$'
        for rec in self:
            if rec.phone:
                if not re.match(phone_regex, rec.phone):
                    raise ValidationError('رقم الهاتف يجب أن يتكون من أرقام فقط (يسمح بإضافة + في البداية) وبطول بين 9 و 15 رقماً.')