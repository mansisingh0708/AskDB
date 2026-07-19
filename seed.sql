-- ═══════════════════════════════════════════════════════════════════════════
-- AskDB — Sample Target Database (sales_db)
-- Run this to create a small sales database for testing.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS sales_db;
USE sales_db;

-- ─── Tables ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50) DEFAULT 'India',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    unit_price DECIMAL(10,2) NOT NULL,
    stock_qty INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date DATETIME NOT NULL,
    status ENUM('pending','completed','cancelled','refunded') DEFAULT 'completed',
    order_total DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- ─── Seed Data ───────────────────────────────────────────────────────────

-- Customers
INSERT INTO customers (name, email, city, state, country) VALUES
('Aarav Sharma', 'aarav@example.com', 'Mumbai', 'Maharashtra', 'India'),
('Priya Patel', 'priya@example.com', 'Delhi', 'Delhi', 'India'),
('Rahul Gupta', 'rahul@example.com', 'Bangalore', 'Karnataka', 'India'),
('Sneha Reddy', 'sneha@example.com', 'Hyderabad', 'Telangana', 'India'),
('Vikram Singh', 'vikram@example.com', 'Mumbai', 'Maharashtra', 'India'),
('Ananya Iyer', 'ananya@example.com', 'Chennai', 'Tamil Nadu', 'India'),
('Rohan Mehta', 'rohan@example.com', 'Pune', 'Maharashtra', 'India'),
('Kavya Nair', 'kavya@example.com', 'Bangalore', 'Karnataka', 'India'),
('Aditya Joshi', 'aditya@example.com', 'Delhi', 'Delhi', 'India'),
('Meera Das', 'meera@example.com', 'Kolkata', 'West Bengal', 'India'),
('Arjun Kumar', 'arjun@example.com', 'Mumbai', 'Maharashtra', 'India'),
('Diya Verma', 'diya@example.com', 'Jaipur', 'Rajasthan', 'India'),
('Siddharth Rao', 'siddharth@example.com', 'Hyderabad', 'Telangana', 'India'),
('Ishita Kapoor', 'ishita@example.com', 'Delhi', 'Delhi', 'India'),
('Nikhil Agarwal', 'nikhil@example.com', 'Lucknow', 'Uttar Pradesh', 'India');

-- Products
INSERT INTO products (name, category, unit_price, stock_qty) VALUES
('Wireless Earbuds Pro', 'Electronics', 2999.00, 150),
('USB-C Hub 7-in-1', 'Electronics', 1499.00, 200),
('Mechanical Keyboard', 'Electronics', 4599.00, 80),
('Cotton T-Shirt Pack', 'Clothing', 899.00, 500),
('Running Shoes Ultra', 'Footwear', 3499.00, 120),
('Yoga Mat Premium', 'Fitness', 1299.00, 300),
('Stainless Steel Bottle', 'Kitchen', 599.00, 400),
('Laptop Stand Adjustable', 'Electronics', 1999.00, 100),
('Organic Green Tea 100pk', 'Food & Beverage', 449.00, 600),
('Noise Cancelling Headphones', 'Electronics', 7999.00, 60);

-- Orders (spread across recent months for interesting queries)
INSERT INTO orders (customer_id, order_date, status, order_total) VALUES
-- June 2026
(1, '2026-06-02 10:30:00', 'completed', 4498.00),
(2, '2026-06-05 14:15:00', 'completed', 2999.00),
(3, '2026-06-08 09:00:00', 'completed', 6098.00),
(4, '2026-06-10 16:45:00', 'completed', 1499.00),
(5, '2026-06-12 11:20:00', 'completed', 8498.00),
(6, '2026-06-15 13:00:00', 'completed', 3499.00),
(7, '2026-06-18 10:00:00', 'completed', 899.00),
(8, '2026-06-20 15:30:00', 'completed', 5898.00),
(9, '2026-06-22 08:45:00', 'completed', 9498.00),
(10, '2026-06-25 12:00:00', 'completed', 1299.00),
(1, '2026-06-27 17:00:00', 'completed', 1999.00),
(11, '2026-06-28 14:30:00', 'completed', 4599.00),
(3, '2026-06-29 11:00:00', 'cancelled', 2999.00),
(12, '2026-06-30 09:00:00', 'completed', 3499.00),
-- May 2026
(1, '2026-05-03 10:00:00', 'completed', 2999.00),
(2, '2026-05-07 14:00:00', 'completed', 7999.00),
(5, '2026-05-10 11:00:00', 'completed', 4599.00),
(6, '2026-05-14 09:30:00', 'completed', 899.00),
(8, '2026-05-18 16:00:00', 'completed', 3499.00),
(9, '2026-05-22 13:00:00', 'completed', 1499.00),
(10, '2026-05-25 10:00:00', 'completed', 599.00),
(13, '2026-05-28 15:00:00', 'completed', 5898.00),
-- April 2026
(3, '2026-04-05 10:00:00', 'completed', 4498.00),
(4, '2026-04-10 14:00:00', 'completed', 1299.00),
(7, '2026-04-15 11:30:00', 'completed', 2999.00),
(14, '2026-04-20 09:00:00', 'completed', 7999.00),
(15, '2026-04-25 16:00:00', 'completed', 899.00),
-- March 2026
(1, '2026-03-02 10:00:00', 'completed', 3499.00),
(2, '2026-03-08 14:30:00', 'completed', 1999.00),
(5, '2026-03-15 11:00:00', 'completed', 4599.00),
(9, '2026-03-20 09:00:00', 'completed', 2999.00),
(11, '2026-03-25 16:00:00', 'completed', 449.00);

-- Order Items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
-- June orders
(1, 1, 1, 2999.00), (1, 4, 1, 899.00), (1, 7, 1, 599.00),
(2, 1, 1, 2999.00),
(3, 3, 1, 4599.00), (3, 2, 1, 1499.00),
(4, 2, 1, 1499.00),
(5, 10, 1, 7999.00), (5, 7, 1, 599.00),
(6, 5, 1, 3499.00),
(7, 4, 1, 899.00),
(8, 3, 1, 4599.00), (8, 6, 1, 1299.00),
(9, 10, 1, 7999.00), (9, 2, 1, 1499.00),
(10, 6, 1, 1299.00),
(11, 8, 1, 1999.00),
(12, 3, 1, 4599.00),
(13, 1, 1, 2999.00),
(14, 5, 1, 3499.00),
-- May orders
(15, 1, 1, 2999.00),
(16, 10, 1, 7999.00),
(17, 3, 1, 4599.00),
(18, 4, 1, 899.00),
(19, 5, 1, 3499.00),
(20, 2, 1, 1499.00),
(21, 7, 1, 599.00),
(22, 3, 1, 4599.00), (22, 6, 1, 1299.00),
-- April orders
(23, 1, 1, 2999.00), (23, 2, 1, 1499.00),
(24, 6, 1, 1299.00),
(25, 1, 1, 2999.00),
(26, 10, 1, 7999.00),
(27, 4, 1, 899.00),
-- March orders
(28, 5, 1, 3499.00),
(29, 8, 1, 1999.00),
(30, 3, 1, 4599.00),
(31, 1, 1, 2999.00),
(32, 9, 3, 449.00);

-- ─── Create read-only user ──────────────────────────────────────────────

-- CREATE USER IF NOT EXISTS 'askdb_readonly'@'localhost' IDENTIFIED BY 'readonly_password';
-- GRANT SELECT ON sales_db.* TO 'askdb_readonly'@'localhost';
-- FLUSH PRIVILEGES;

-- ═══════════════════════════════════════════════════════════════════════════
-- App Database (for Django ORM models)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS askdb_app;
