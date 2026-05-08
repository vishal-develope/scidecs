# -*- coding: utf-8 -*-
{
    'name': 'Steel Invoice Items',
    'version': '1.0.0',
    'category': 'Accounting',
    'summary': 'Steel trading and manufacturing invoice lines with stock move integration',
    'description': 'Add a Steel Items tab on invoices and bills, auto-generate invoice lines and stock pickings from steel item details.',
    'author': 'Custom',
    'license': 'AGPL-3',
    'depends': ['account', 'stock', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
