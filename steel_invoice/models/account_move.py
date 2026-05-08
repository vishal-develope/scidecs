# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class SteelInvoiceLine(models.Model):
    _name = 'steel.invoice.line'
    _description = 'Steel Invoice Item'
    _order = 'id asc'

    move_id = fields.Many2one(
        'account.move',
        string='Invoice',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product / Item',
        domain="[('type', 'in', ('product', 'consu'))]",
    )
    make = fields.Selection([
        ('sail_jindal', 'SAIL/JINDAL'),
        ('rolling', 'ROLLING'),
    ], string='Make', required=True, default='sail_jindal')
    description = fields.Char(string='Description')
    thickness = fields.Float(string='Thickness (mm)', digits='Product Unit')
    width = fields.Float(string='Width (mm)', digits='Product Unit')
    length_mm = fields.Float(string='Length (mm)', digits='Product Unit')
    length_meter = fields.Char(string='Length (Meter)')
    grade = fields.Char(string='Grade')
    qty_nos = fields.Float(string='Qty Nos', digits='Product Unit')
    qty_mt = fields.Float(string='Qty MT', digits='Product Unit')
    rate_mt = fields.Float(string='Rate per MT', digits='Product Price')
    amount = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        store=True,
        readonly=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='move_id.currency_id',
        string='Currency',
        readonly=True,
        store=True,
    )
    invoice_line_id = fields.Many2one(
        'account.move.line',
        string='Invoice Line',
        copy=False,
    )
    remark = fields.Char(string='Remark')


    @api.onchange('product_id')
    def _onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.rate_mt = record.product_id.with_company(record.move_id.company_id).list_price or 0.0
            else:
                record.rate_mt = 0.0

    @api.onchange('make')
    def _onchange_make(self):
        for record in self:
            if record.make == 'sail_jindal':
                record.description = False
                record.length_meter = False
            elif record.make == 'rolling':
                record.thickness = False
                record.width = False
                record.length_mm = False
                record.qty_nos = 0.0
            else:
                record.description = False
                record.length_meter = False
                record.thickness = False
                record.width = False
                record.length_mm = False
                record.qty_nos = 0.0

    @api.depends('qty_mt', 'rate_mt')
    def _compute_amount(self):
        for record in self:
            record.amount = (record.qty_mt or 0.0) * (record.rate_mt or 0.0)

    @api.model
    def create(self, vals):
        record = super().create(vals)
        # Removed: record._sync_invoice_lines_for_draft_moves()
        return record

    def write(self, vals):
        res = super().write(vals)
        # Removed: self._sync_invoice_lines_for_draft_moves()
        return res

    def unlink(self):
        """Remove linked invoice lines when steel line is deleted from draft invoices."""
        invoice_lines = self.filtered(lambda r: r.move_id.state == 'draft' and r.invoice_line_id and r.invoice_line_id.exists()).mapped('invoice_line_id')
        res = super().unlink()
        if invoice_lines:
            invoice_lines.filtered(lambda line: line.move_id.state == 'draft').sudo().unlink()
        return res

    def _sync_invoice_lines_for_draft_moves(self):
        """
        Sync steel invoice lines to account.move.line for draft invoices.
        
        Rules:
        - Only sync for draft invoices with products
        - Create or update invoice_line_id for each steel_line
        - Use stable link: steel_line_id on invoice line, invoice_line_id on steel line
        - Remove orphaned steel-linked lines only if the steel line no longer exists
        - Do NOT delete non-linked invoice lines (user may have created them manually)
        - Do NOT use unlink() aggressively while form is open
        """
        steel_lines = self.filtered(lambda line: line.move_id.state == 'draft' and line.product_id)
        if not steel_lines:
            return

        for invoice_move in steel_lines.mapped('move_id'):
            if invoice_move.state != 'draft':
                continue
            
            move_lines = steel_lines.filtered(lambda line: line.move_id == invoice_move)
            
            for steel_line in move_lines:
                if not steel_line.product_id:
                    continue
                
                vals = invoice_move._get_steel_line_vals(invoice_move, steel_line)
                
                # Get the linked invoice line (if it exists and is still in this move)
                invoice_line = steel_line.invoice_line_id
                if invoice_line and invoice_line.exists() and invoice_line.move_id == invoice_move:
                    # Update the existing linked line
                    invoice_line.sudo().write(vals)
                else:
                    # No linked line or it was deleted, create a new one
                    invoice_line = self.env['account.move.line'].sudo().create(vals)
                    steel_line.sudo().write({'invoice_line_id': invoice_line.id})
            
            # Clean up: remove orphaned steel-linked invoice lines
            # (lines with steel_line_id that no longer have a corresponding steel line)
            all_steel_ids = move_lines.ids
            orphaned_lines = invoice_move.invoice_line_ids.filtered(
                lambda line: line.move_id.state == 'draft' and 
                           line.steel_line_id and 
                           line.steel_line_id.id not in all_steel_ids and
                           not line.steel_line_id.exists()
            )
            if orphaned_lines:
                orphaned_lines.sudo().unlink()


class AccountMove(models.Model):
    _inherit = 'account.move'

    steel_line_ids = fields.One2many(
        'steel.invoice.line',
        'move_id',
        string='Steel Items',
        copy=True,
    )
    steel_picking_ids = fields.Many2many(
        'stock.picking',
        compute='_compute_steel_picking_ids',
        string='Steel Delivery Orders',
    )
    steel_picking_count = fields.Integer(
        string='Delivery Orders',
        compute='_compute_steel_picking_ids',
    )
    steel_picking_id = fields.Many2one(
        'stock.picking',
        string='Steel Delivery Order',
        copy=False,
    )
    steel_stock_done = fields.Boolean(
        string='Steel Stock Done',
        default=False,
        copy=False,
    )
    is_from_sale_order = fields.Boolean(
        string='Is From Sale Order',
        compute='_compute_is_from_sale_order',
        store=False,
    )
    is_steel_invoice = fields.Boolean(
        string='Steel Invoice',
        copy=False,
        readonly=True,
    )


    has_rolling = fields.Boolean(compute='_compute_steel_make_types')
    has_sail_jindal = fields.Boolean(compute='_compute_steel_make_types')

    @api.depends('steel_line_ids.make')
    def _compute_steel_make_types(self):
        for rec in self:
            makes = rec.steel_line_ids.mapped('make')
            rec.has_rolling = 'rolling' in makes
            rec.has_sail_jindal = 'sail_jindal' in makes


    @api.depends('invoice_line_ids')
    def _compute_is_from_sale_order(self):
        
        for move in self:
            move.is_from_sale_order = any(line.sale_line_ids for line in move.invoice_line_ids)
    
    
    
    def action_post(self):
        # Create invoice lines from steel lines for all steel invoices before posting
        steel_moves = self.filtered(
            lambda m: m.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund', 'out_receipt', 'in_receipt') and
                     m.steel_line_ids
        )

        if steel_moves:
            # Create invoice lines from steel lines for all steel invoices
            steel_moves._create_or_update_steel_invoice_lines()

        # Run steel logic for direct invoices with steel lines
        direct_steel_moves = self.filtered(
            lambda m: m.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund', 'out_receipt', 'in_receipt') and
                     not m.is_from_sale_order and m.steel_line_ids
        )

        if direct_steel_moves:
            # Validate stock availability for direct invoices
            direct_steel_moves._validate_steel_stock_availability()

        result = super().action_post()

        if direct_steel_moves:
            direct_steel_moves._create_steel_stock_pickings()

        # Handle Sale Order based steel invoices
        sale_order_steel_moves = self.filtered(
            lambda m: m.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund', 'out_receipt', 'in_receipt') and
                     m.is_from_sale_order and m.is_steel_invoice and m.state == 'posted'
        )
        if sale_order_steel_moves:
            sale_order_steel_moves._create_sale_order_steel_deliveries()

        return result

    @api.depends('name', 'company_id')
    def _compute_steel_picking_ids(self):
        for move in self:
            if not move.name:
                move.steel_picking_ids = self.env['stock.picking'].browse()
                move.steel_picking_count = 0
                continue
            origins = [move.name]
            if move.invoice_origin:
                origins.append(move.invoice_origin)
            
            
            picks = self.env['stock.picking'].search([
                ('origin', '=', move.name),
                ('company_id', '=', move.company_id.id),
                ('picking_type_id.code', '=', 'outgoing'),
            ])
            move.steel_picking_ids = picks
            move.steel_picking_count = len(picks)

    def action_view_steel_pickings(self):
        self.ensure_one()
        action = self.env.ref('stock.action_picking_tree_all', raise_if_not_found=False)
        if action:
            result = action.read()[0]
        else:
            result = {
                'name': _('Delivery'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'list,form',
            }
        result['domain'] = [('id', 'in', self.steel_picking_ids.ids)]
        result['context'] = {'default_origin': self.name}
        if len(self.steel_picking_ids) == 1:
            result['res_id'] = self.steel_picking_ids.id
            result['views'] = [(self.env.ref('stock.view_picking_form', raise_if_not_found=False).id, 'form')]
        return result

    def _get_steel_invoice_account(self, move, product):
        accounts = product.with_company(move.company_id)._get_product_accounts()
        if move.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
            return accounts.get('income')
        return accounts.get('expense')

    def _get_steel_line_vals(self, move, steel_line):
        product = steel_line.product_id
        if not product:
            raise UserError(_('Steel item line %s must have a product.') % (steel_line.id,))

        account = self._get_steel_invoice_account(move, product)
        if not account:
            raise UserError(_('No income/expense account configured for product %s.') % product.display_name)

        return {
            'move_id': move.id,
            'product_id': product.id,
            'name': self._get_steel_invoice_line_name(steel_line),
            'quantity': steel_line.qty_mt or 0.0,
            'product_uom_id': product.uom_id.id,
            'price_unit': steel_line.rate_mt or 0.0,
            'account_id': account.id,
            'steel_line_id': steel_line.id,
        }

    def _get_steel_invoice_line_name(self, steel_line):
        pieces = [dict(steel_line._fields['make'].selection).get(steel_line.make, steel_line.make or '')]
        if steel_line.make == 'sail_jindal':
            if steel_line.thickness:
                pieces.append(_('%s mm') % (steel_line.thickness,))
            if steel_line.width:
                pieces.append(_('%s mm') % (steel_line.width,))
            if steel_line.length_mm:
                pieces.append(_('%s mm') % (steel_line.length_mm,))
        elif steel_line.make == 'rolling':
            if steel_line.description:
                pieces.append(steel_line.description)
            if steel_line.length_meter:
                pieces.append(steel_line.length_meter)
        if steel_line.grade:
            pieces.append(steel_line.grade)
        return ' '.join(str(p).strip() for p in pieces if p)

    
    def _validate_steel_stock_availability(self):
        # Only validate outgoing customer invoices because only these reduce stock.
        internal_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        if not internal_location:
            raise ValidationError(_('Source stock location WH/Stock is not configured.'))

        for move in self.filtered(lambda m: m.move_type == 'out_invoice'):
            requested_by_product = {}
            for steel_line in move.steel_line_ids.filtered('product_id'):
                qty_mt = steel_line.qty_mt or 0.0
                if qty_mt <= 0.0:
                    continue
                requested_by_product.setdefault(steel_line.product_id, 0.0)
                requested_by_product[steel_line.product_id] += qty_mt

            for product, total_qty_mt in requested_by_product.items():
                available_quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', 'child_of', internal_location.id),
                ])
                available_qty = sum(available_quants.mapped('quantity'))
                if float(available_qty) + 1e-9 < float(total_qty_mt):
                    raise ValidationError(_('%(product)s does not have enough stock in %(location)s: required %(required).4f %(uom)s, available %(available).4f %(uom)s.') % {
                        'product': product.display_name,
                        'location': internal_location.display_name,
                        'required': total_qty_mt,
                        'uom': product.uom_id.name,
                        'available': available_qty,
                    })

    def _create_or_update_steel_invoice_lines(self):
        # Only create invoice lines from steel lines for direct invoices
        for move in self:
            sale_orders = move.invoice_line_ids.mapped('sale_line_ids.order_id')
            is_steel_order = any(sale_orders.mapped('is_steel_order'))
            if is_steel_order:
                
                invoice_moves = self.filtered(
                    lambda move: move.move_type in (
                        'out_invoice', 'in_invoice', 'out_refund', 'in_refund', 'out_receipt', 'in_receipt'
                    ) and move.steel_line_ids
                )
            else: 
                invoice_moves = self.filtered(
                    lambda move: move.move_type in (
                        'out_invoice', 'in_invoice', 'out_refund', 'in_refund', 'out_receipt', 'in_receipt'
                    ) and not move.is_from_sale_order and move.steel_line_ids
                )

        for move in invoice_moves:
            existing_lines = move.invoice_line_ids.filtered(lambda line: line.steel_line_id)
            kept_lines = self.env['account.move.line']
            for steel_line in move.steel_line_ids:
                if not steel_line.product_id:
                    continue
                vals = self._get_steel_line_vals(move, steel_line)
                if steel_line.invoice_line_id and steel_line.invoice_line_id in existing_lines:
                    steel_line.invoice_line_id.sudo().write(vals)
                    kept_lines |= steel_line.invoice_line_id
                else:
                    invoice_line = self.env['account.move.line'].sudo().create(vals)
                    steel_line.invoice_line_id = invoice_line.id
                    kept_lines |= invoice_line
            obsolete_lines = existing_lines - kept_lines
            if obsolete_lines:
                obsolete_lines.sudo().unlink()

    def _get_stock_location(self, usage, company):
        location = self.env['stock.location']
        external = self.env.ref(
            'stock.stock_location_%s' % usage,
            raise_if_not_found=False,
        )
        if external:
            return external
        return location.search([('usage', '=', usage), ('company_id', '=', company.id)], limit=1)

    def _get_picking_type(self, code, company):
        picking_type = self.env['stock.picking.type'].with_company(company).search(
            [('code', '=', code), ('company_id', '=', company.id)],
            limit=1,
        )
        if picking_type:
            return picking_type
        return self.env['stock.picking.type'].with_company(company).search(
            [('code', '=', code)],
            limit=1,
        )

    def _create_sale_order_steel_deliveries(self):
        """Create delivery orders for Sale Order based steel invoices from invoice lines."""
        _logger.info('=== Starting _create_sale_order_steel_deliveries for %d moves ===', len(self))
        pickings = self.env['stock.picking']
        internal_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        customer_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        
        if not internal_location or not customer_location:
            _logger.error('Sale order steel delivery creation skipped: missing stock/customer location.')
            return
        
        for move in self:
            if move.move_type != 'out_invoice':
                continue
            
            # Get the sale order from invoice lines
            sale_orders = self.env['sale.order']
            for invoice_line in move.invoice_line_ids:
                sale_orders |= invoice_line.sale_line_ids.mapped('order_id')
            
            for sale_order in sale_orders:
                if not sale_order.is_steel_order:
                    continue
                
                _logger.info('Processing steel sale order invoice %s for sale order %s', move.name, sale_order.name)
                
                # Create move lines from invoice lines (all stockable products)
                move_lines = []
                
                for invoice_line in move.invoice_line_ids:
                    if not invoice_line.product_id or invoice_line.product_id.type not in ('product', 'consu'):
                        continue
                    
                    qty = invoice_line.quantity
                    product_uom = invoice_line.product_uom_id
                    
                    if qty <= 0.0:
                        continue
                    
                    move_lines.append((0, 0, {
                        'product_id': invoice_line.product_id.id,
                        'product_uom_qty': qty,
                        'product_uom': product_uom.id,
                        'location_id': internal_location.id,
                        'location_dest_id': customer_location.id,
                        'picking_type_id': self._get_picking_type('outgoing', move.company_id).id,
                        'company_id': move.company_id.id,
                    }))
                
                if not move_lines:
                    _logger.warning('No stockable invoice lines found for sale order %s', sale_order.name)
                    continue
                
                picking_type = self._get_picking_type('outgoing', move.company_id)
                if not picking_type:
                    _logger.error('Outgoing picking type not found for company %s', move.company_id.name)
                    continue
                
                try:
                    picking_vals = {
                        'partner_id': move.partner_id.id,
                        'picking_type_id': picking_type.id,
                        'location_id': internal_location.id,
                        'location_dest_id': customer_location.id,
                        'origin': move.name if sale_order.is_steel_order else sale_order.name,
                        'company_id': move.company_id.id,
                        'move_ids': move_lines,
                    }
                    _logger.info('Creating delivery for steel sale order %s with %d items', sale_order.name, len(move_lines))
                    picking = self.env['stock.picking'].sudo().create(picking_vals)
                    
                    try:
                        picking.action_confirm()
                        picking.with_context(skip_sanity_check=True).button_validate()
                        _logger.info('Delivery created and validated: %s', picking.name)
                    except Exception as exc:
                        _logger.error('Delivery created but not validated for sale order %s: %s', sale_order.name, exc)
                except Exception as exc:
                    _logger.error('Failed to create delivery for steel sale order %s: %s', sale_order.name, exc)

    def _create_steel_stock_pickings(self):
        """Create and validate outgoing stock pickings for direct customer invoices."""
        _logger.info('=== Starting _create_steel_stock_pickings for %d moves ===', len(self))
        pickings = self.env['stock.picking']
        internal_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        customer_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        
        _logger.info('Internal Location: %s, Customer Location: %s', 
                     internal_location.name if internal_location else 'NOT FOUND',
                     customer_location.name if customer_location else 'NOT FOUND')
        
        if not internal_location or not customer_location:
            _logger.error('Steel stock picking creation skipped: missing stock/customer location.')
            return

        filtered_moves = self.filtered(lambda m: m.state == 'posted' and m.move_type == 'out_invoice' and m.steel_line_ids and not m.steel_stock_done and not m.is_from_sale_order)
        _logger.info('Filtered moves (posted + out_invoice + has steel_lines + not stock_done + not from sale order): %d', len(filtered_moves))
        
        for idx, move in enumerate(filtered_moves):
            _logger.info('Processing move %d/%d: %s (state=%s, type=%s, steel_lines=%d)', 
                        idx+1, len(filtered_moves), move.name, move.state, move.move_type, len(move.steel_line_ids))
            

            
            # This is a direct invoice (not from sale order), create picking from steel lines
            picking_type = self._get_picking_type('outgoing', move.company_id)
            if not picking_type:
                _logger.error('Outgoing picking type missing for company %s', move.company_id.name)
                continue
            _logger.info('Creating delivery from steel lines for direct invoice %s', move.name)
            _logger.info('Picking type found: %s', picking_type.name)

            existing_picking = pickings.search([
                ('origin', '=', move.name),
                ('picking_type_id', '=', picking_type.id),
                ('company_id', '=', move.company_id.id),
            ], limit=1)
            if existing_picking:
                _logger.info('Existing picking found: %s (state=%s)', existing_picking.name, existing_picking.state)
                if existing_picking.state != 'done':
                    try:
                        existing_picking.action_confirm()
                        existing_picking.with_context(skip_sanity_check=True).button_validate()
                    except Exception as exc:
                        _logger.error('Failed to validate existing steel picking for invoice %s: %s', move.name or move.id, exc)
                move.steel_picking_id = existing_picking
                move.steel_stock_done = True
                continue

            move_lines = []
            for steel_line in move.steel_line_ids.filtered('product_id'):
                qty_mt = steel_line.qty_mt or 0.0
                product_uom = steel_line.product_id.uom_id
                _logger.info('Steel line: product=%s, qty_mt=%s, product_uom=%s', steel_line.product_id.name, qty_mt, product_uom.name)
                if qty_mt <= 0.0:
                    _logger.info('Skipping steel line (qty_mt <= 0)')
                    continue
                move_lines.append((0, 0, {
                    'product_id': steel_line.product_id.id,
                    'product_uom_qty': qty_mt,
                    'product_uom': product_uom.id,
                    'location_id': internal_location.id,
                    'location_dest_id': customer_location.id,
                    'picking_type_id': picking_type.id,
                    'company_id': move.company_id.id,
                }))

            if not move_lines:
                _logger.warning('No move lines created for invoice %s (all steel lines filtered out)', move.name)
                move.steel_stock_done = True
                continue

            try:
                picking_vals = {
                    'partner_id': move.partner_id.id,
                    'picking_type_id': picking_type.id,
                    'location_id': internal_location.id,
                    'location_dest_id': customer_location.id,
                    'origin': move.name,
                    'company_id': move.company_id.id,
                    'move_ids': move_lines,
                }
                _logger.info('Creating picking for invoice %s with %d move lines', move.name, len(move_lines))
                picking = self.env['stock.picking'].sudo().create(picking_vals)
                _logger.info('Picking created: %s', picking.name)
                move.steel_picking_id = picking
                try:
                    picking.action_confirm()
                    _logger.info('Picking confirmed: %s', picking.name)
                    picking.with_context(skip_sanity_check=True).button_validate()
                    _logger.info('Picking validated: %s', picking.name)
                    move.steel_stock_done = True
                except Exception as exc:
                    _logger.error('Steel picking created but not validated for invoice %s: %s', move.name or move.id, exc)
            except Exception as exc:
                _logger.error('Failed to create steel stock picking for invoice %s: %s', move.name or move.id, exc)
                import traceback
                _logger.error(traceback.format_exc())
                continue


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    steel_line_id = fields.Many2one(
        'steel.invoice.line',
        string='Steel Item',
        copy=False,
        ondelete='set null',
    )
