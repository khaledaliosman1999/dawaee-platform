{
    'name': 'منصة دوائي',
    'version': '18.0.1.0.0',
    'summary': 'منصة إلكترونية متكاملة لإدارة وتوفير الأدوية المزمنة والنادرة',
    'description': """
        نظام إدارة الأدوية للصيدليات في الخرطوم
        جامعة السودان للعلوم والتكنولوجيا — قسم نظم المعلومات الإدارية 2026
    """,
    'author': 'Khaled Aili Osman Sudan University of Science and Technology - MIS Dept.',
    'category': 'Healthcare',
    'depends': ['base', 'website', 'mail'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/medicine_views.xml',
        'views/supplier_pharmacy_patient_views.xml',
        'views/stock_inbound_inventory_views.xml',
        'views/booking_prescription_dispensing_views.xml',
        'views/website_templates.xml',
        'views/portal_pharmacist_templates.xml',
        'data/cron.xml',

        'views/menu_views.xml',

    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
