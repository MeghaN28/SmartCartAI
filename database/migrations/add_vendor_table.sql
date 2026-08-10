-- Normalize vendor_id into a proper reference table instead of a bare code
-- repeated on inventory/sales with no lookup entity (3NF: vendor attributes
-- depend on vendor_id, not on inventory_id or invoice_id).
-- Run: psql -h localhost -U your_user -d smartcart_ai -f database/migrations/add_vendor_table.sql

CREATE TABLE IF NOT EXISTS vendor (
  vendor_id VARCHAR(32) PRIMARY KEY,
  name TEXT NOT NULL,
  contact_email TEXT,
  phone VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed vendor names for the synthetic V001-V010 codes already present in inventory/sales.
INSERT INTO vendor (vendor_id, name, contact_email, phone) VALUES
  ('V001', 'Golden Gate Wholesale Foods', 'orders@ggwholesalefoods.example', '415-555-0101'),
  ('V002', 'Bay Area Fresh Distributors', 'sales@bayareafresh.example',    '415-555-0102'),
  ('V003', 'Cascade Dairy & Beverage Co.', 'orders@cascadedairy.example',  '415-555-0103'),
  ('V004', 'Sunrise Produce Partners',     'sales@sunriseproduce.example', '415-555-0104'),
  ('V005', 'Pacific Bakery Supply',        'orders@pacificbakery.example', '415-555-0105'),
  ('V006', 'Harbor Point Grocers Supply',  'sales@harborpoint.example',    '415-555-0106'),
  ('V007', 'Evergreen Snack Distribution', 'orders@evergreensnack.example','415-555-0107'),
  ('V008', 'Northgate Foodservice Group',  'sales@northgatefood.example',  '415-555-0108'),
  ('V009', 'Redwood Valley Suppliers',     'orders@redwoodvalley.example', '415-555-0109'),
  ('V010', 'Marina District Provisions',   'sales@marinaprovisions.example','415-555-0110')
ON CONFLICT (vendor_id) DO NOTHING;

-- Add FK constraints now that every vendor_id in use has a matching row.
-- NOT VALID + VALIDATE avoids locking issues on larger tables; here it's instant either way.
ALTER TABLE inventory
  ADD CONSTRAINT fk_inventory_vendor FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id);

ALTER TABLE sales
  ADD CONSTRAINT fk_sales_vendor FOREIGN KEY (vendor_id) REFERENCES vendor(vendor_id);

CREATE INDEX IF NOT EXISTS idx_inventory_vendor ON inventory(vendor_id);
CREATE INDEX IF NOT EXISTS idx_sales_vendor ON sales(vendor_id);
