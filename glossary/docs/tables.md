# Database Tables Reference

## `customers` Table
| Column | Type | Description |
|--------|------|-------------|
| customer_id | INT (PK) | Unique customer identifier |
| name | VARCHAR(100) | Full name of the customer |
| email | VARCHAR(150) | Email address (unique) |
| city | VARCHAR(100) | City of residence |
| state | VARCHAR(50) | State / region |
| country | VARCHAR(50) | Country, default 'India' |
| created_at | DATETIME | When the customer registered |

## `products` Table
| Column | Type | Description |
|--------|------|-------------|
| product_id | INT (PK) | Unique product identifier |
| name | VARCHAR(200) | Product display name |
| category | VARCHAR(100) | Product category (e.g. Electronics, Clothing) |
| unit_price | DECIMAL(10,2) | Price per unit in INR |
| stock_qty | INT | Current stock quantity |

## `orders` Table
| Column | Type | Description |
|--------|------|-------------|
| order_id | INT (PK) | Unique order identifier |
| customer_id | INT (FK → customers) | Who placed the order |
| order_date | DATETIME | When the order was placed |
| status | ENUM('pending','completed','cancelled','refunded') | Order status |
| order_total | DECIMAL(12,2) | Total amount of the order |

## `order_items` Table
| Column | Type | Description |
|--------|------|-------------|
| item_id | INT (PK) | Unique item identifier |
| order_id | INT (FK → orders) | Which order this belongs to |
| product_id | INT (FK → products) | Which product |
| quantity | INT | Number of units ordered |
| unit_price | DECIMAL(10,2) | Price at time of order |

## Important Relationships
- One customer → many orders → many order_items → one product each
- Always join on `orders.status = 'completed'` unless asked about cancelled/pending orders
- Use `order_items.unit_price` (not `products.unit_price`) for historical revenue — products.unit_price may have changed
