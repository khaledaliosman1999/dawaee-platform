# -*- coding: utf-8 -*-
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    pharmacy_id = fields.Many2one(
        comodel_name='dawai.pharmacy',
        string='الصيدلية التابع لها',
        help='تحديد الصيدلية هنا يضمن أن هذا المستخدم لن يرى إلا بيانات هذه الصيدلية في الواجهة.'
    )