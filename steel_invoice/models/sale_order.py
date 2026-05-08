# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_steel_order = fields.Boolean(string="Steel Order")

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals['is_steel_invoice'] = self.is_steel_order
        return invoice_vals