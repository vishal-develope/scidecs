# Steel Invoice Module for Odoo 19

Hey there! 👋 This is a custom module I built for Odoo 19 that makes handling steel invoices a whole lot easier. If you're dealing with steel products and need detailed item specifications on your invoices, this module is for you.

## What This Module Does

Imagine you're selling steel products - you don't just sell "steel", you sell specific types with measurements, grades, and quantities. This module adds a dedicated "Steel Items" section to your customer invoices where you can capture all those important details.

### Key Features

- **Steel Items Tab**: A clean, organized tab on customer invoices for steel product details
- **Detailed Specifications**: Track make (SAIL/JINDAL or Rolling), thickness, width, length, grade, and quantities
- **Smart Calculations**: Automatically calculates amounts and fills product prices
- **Seamless Integration**: Creates proper invoice lines and delivery orders automatically
- **Stock Validation**: Checks if you have enough steel in stock before confirming invoices
- **Sale Order Support**: Works with both direct invoices and invoices created from sale orders

## Quick Start Guide

### Installation Steps

1. **Download and Place the Module**
   ```
   Copy the 'steel_invoice' folder to your Odoo custom_addons directory
   ```

2. **Restart Your Odoo Server**
   ```bash
   # Stop Odoo if it's running
   # Then restart with your usual command
   ```

3. **Update Apps List**
   - Go to Odoo → Apps → Update Apps List
   - Or run this from command line if you prefer

4. **Install the Module**
   - Search for "Steel Invoice" in the Apps menu
   - Click Install on the "Steel Invoice Items" module

5. **Verify Installation**
   - Create a new customer invoice
   - You should see a "Steel Items" tab

### Basic Configuration

Before using the module extensively, make sure:

- **Products**: Steel products are set up with correct UOMs and prices
- **UOMs**: Make sure you have "MT" (Metric Ton) unit of measure

## How to Use It

### For Direct Customer Invoices

1. **Create Invoice**: Invoices → Create
2. **Add Customer Details**: Fill in customer, invoice date, etc.
3. **Steel Items Tab**: Click on the "Steel Items" tab
4. **Add Steel Lines**: Click "Add a line" and fill in:
   - **Product**: Select your steel product
   - **Make**: Choose SAIL/JINDAL or Rolling
   - **Details**: Fill thickness, width, length, grade based on make
   - **Quantities**: Enter qty_nos (pieces) and qty_mt (metric tons)
   - **Rate**: Price per metric ton (auto-fills from product price)
5. **Review**: The amount calculates automatically
6. **Post Invoice**: Click "Confirm" - this creates invoice lines AND delivery orders

### For Sale Order Based Invoices

1. **Create Sale Order**: With steel products and mark as "Steel Order"
2. **Confirm Sale Order**: This creates the invoice automatically
3. **Steel Items**: The invoice will have steel items pre-filled from the sale order
4. **Post Invoice**: Creates delivery orders linked to the sale order

## The Technical Approach

I designed this module with a clean separation of concerns:

### Data Model
- **`steel.invoice.line`**: Stores detailed steel specifications
- **Enhanced `account.move`**: Adds steel items relationship and computed fields
- **Enhanced `account.move.line`**: Links back to steel lines

### Business Logic Flow

1. **Draft State**: Steel items are managed separately from invoice lines
2. **Posting Trigger**: When invoice is confirmed, steel items become invoice lines
3. **Stock Integration**: Automatic delivery order creation with proper stock moves
4. **Validation**: Stock availability checks before allowing invoice confirmation

### Key Design Decisions

- **Post-Only Sync**: Invoice lines are created only when posting (not during draft editing)
- **Stable Linking**: Bidirectional links between steel lines and invoice lines
- **Safe Copying**: Handles invoice duplication without creating duplicates
- **Flexible Origins**: Delivery orders use appropriate origin references

## Dependencies

- **Core Odoo Modules**: `account`, `stock`, `product`
- **Python**: Standard library (no external dependencies)
- **Database**: Works with PostgreSQL (standard Odoo setup)

## Troubleshooting

### Common Issues

**"Steel Items tab not showing"**
- Make sure the module is installed and active
- Check if you're on a customer invoice (not vendor bill)

**"Cannot post invoice - stock validation error"**
- Check your warehouse stock levels
- Verify product quantities are correct

**"Delivery order not created"**
- Ensure stock locations are properly configured
- Check Odoo logs for any error messages

### Getting Help

If you run into issues:
1. Check the Odoo server logs for error messages
2. Verify all dependencies are installed
3. Make sure your Odoo version is 19.0

## Version History

- **v1.0**: Initial release with basic steel invoice functionality
- **v1.1**: Added sale order integration and improved stock handling

---

