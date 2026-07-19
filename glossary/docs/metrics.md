# Business Metrics Glossary

## Revenue
- **Total Revenue**: Sum of all `order_total` in the `orders` table where `status = 'completed'`.
- **Monthly Revenue**: Revenue grouped by `DATE_FORMAT(order_date, '%Y-%m')`.
- **Average Order Value (AOV)**: `SUM(order_total) / COUNT(DISTINCT order_id)` for completed orders.

## Customers
- **Active Customer**: A customer with at least 1 completed order in the last 30 days.
- **New Customer**: A customer whose `created_at` date is within the last 30 days.
- **Customer Lifetime Value (CLV)**: Total revenue from all orders placed by a single customer.

## Orders
- **Completed Order**: An order where `status = 'completed'`. Excludes cancelled, pending, and refunded.
- **Last Month**: Refers to the period from the first to the last day of the previous calendar month. Use `DATE_SUB(CURDATE(), INTERVAL 1 MONTH)`.
- **Order Count**: `COUNT(DISTINCT order_id)` — always count distinct to avoid duplicates from joins.

## Products
- **Top Selling Product**: Product with the highest `SUM(quantity)` across completed order items.
- **Product Revenue**: `SUM(quantity * unit_price)` from `order_items` joined with completed orders.
