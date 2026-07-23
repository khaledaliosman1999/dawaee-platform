# ============================================================
# جدول 1: الأدوية (Medicines Table)
# يمثل كينونة الدواء وبياناته الأساسية
# ============================================================

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DawaiMedicine(models.Model):
    _name = 'dawai.medicine'
    _description = 'جدول الأدوية'
    _rec_name = 'med_name'
    _order = 'med_name asc'
    # mail.thread: لتتبع التغييرات على السجل
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── الحقول الأساسية ─────────────────────────────────
    med_name = fields.Char(
        string='الاسم التجاري',
        size=50,
        required=True,
        tracking=True,
        help='الاسم التجاري للدواء كما يظهر على العبوة',
    )
    scientific_name = fields.Char(
        string='الاسم العلمي',
        size=50,
        required=True,
        tracking=True,
        help='الاسم العلمي (Generic Name) للمادة الفعالة',
    )
    med_category = fields.Selection(
        selection=[
            ('diabetes','سكري'),
            ('pressure','ضغط دم'),
            ('heart','قلب'),
            ('asthma','ربو'),
            ('rare','دواء نادر'),
            ('emergency','طوارئ / مضاد سموم'),
            ('other','أخرى'),
        ],
        string='تصنيف الدواء',
        tracking=True,
        help='سكري / ضغط / قلب / ربو — كما هو في نطاق البحث',
    )
    med_price = fields.Float(
        string='سعر الدواء (SDG)',
        digits=(10, 2),
        tracking=True,
    )
    requires_prescription = fields.Boolean(
        string='يحتاج وصفة طبية؟',
        default=False,
        tracking=True,
        help='إن كان True لا يمكن الصرف بدون وصفة مسجلة',
    )
    active = fields.Boolean(
        string='نشط',
        default=True,
        tracking=True,
        help='إلغاء التحديد = أرشفة الدواء (Odoo Archive)',
    )

    # ─── حقول محسوبة (Computed) ──────────────────────────
    inventory_count = fields.Integer(
        string='عدد الصيدليات المتوفر بها',
        compute='_compute_inventory_count',
    )
    total_qty_available = fields.Integer(
        string='إجمالي الكمية المتاحة',
        compute='_compute_total_qty',
    )

    # ─── Computed Methods ─────────────────────────────────
    def _compute_inventory_count(self):
        for rec in self:
            rec.inventory_count = self.env['dawai.inventory'].search_count([
                ('med_id', '=', rec.id),
                ('active', '=', True),
            ])

    def _compute_total_qty(self):
        for rec in self:
            inventories = self.env['dawai.inventory'].search([
                ('med_id', '=', rec.id),
                ('active', '=', True),
            ])
            rec.total_qty_available = sum(
                max(inv.qty_available - inv.qty_reserved, 0)
                for inv in inventories
            )

    # ─── Smart Button ─────────────────────────────────────
    def action_view_inventory(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'مخزون {self.med_name}',
            'res_model': 'dawai.inventory',
            'view_mode': 'list,form',
            'domain': [('med_id', '=', self.id)],
            'context': {'default_med_id': self.id},
        }

    # ─── Constraints ──────────────────────────────────────
    @api.constrains('med_price')
    def _check_price(self):
        for rec in self:
            if rec.med_price < 0:
                raise ValidationError('سعر الدواء لا يمكن أن يكون سالباً!')

    _sql_constraints = [
        ('med_name_scientific_unique',
         'UNIQUE(med_name, scientific_name)',
         'يوجد دواء بنفس الاسم التجاري والعلمي مسبقاً!'),
    ]
