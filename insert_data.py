import os
import pymysql
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load database credentials
load_dotenv()

# We connect as root to be able to insert
db_name = "sales_db"
db_user = os.getenv("APP_DB_USER", "root")
db_password = os.getenv("APP_DB_PASSWORD", "Mansi123")
db_host = os.getenv("APP_DB_HOST", "127.0.0.1")
db_port = int(os.getenv("APP_DB_PORT", "3306"))

print(f"Connecting to {db_name} on {db_host}:{db_port} as {db_user}...")
connection = pymysql.connect(
    host=db_host,
    user=db_user,
    password=db_password,
    database=db_name,
    port=db_port,
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with connection.cursor() as cursor:
        # Disable foreign key checks temporarily to make inserts easy (though we will maintain consistency)
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

        # 1. Insert new customers
        new_customers = [
            ('Liam Smith', 'liam@example.com', 'New York', 'New York', 'USA'),
            ('Emma Watson', 'emma@example.com', 'London', 'England', 'UK'),
            ('Oliver Hansen', 'oliver@example.com', 'Toronto', 'Ontario', 'Canada'),
            ('Sophia Brown', 'sophia@example.com', 'Sydney', 'New South Wales', 'Australia'),
            ('Suraj Patil', 'suraj@example.com', 'Surat', 'Gujarat', 'India'),
            ('Karan Johar', 'karan@example.com', 'Mumbai', 'Maharashtra', 'India'),
            ('Neha Kakkar', 'neha@example.com', 'Delhi', 'Delhi', 'India'),
            ('Amit Shah', 'amit@example.com', 'Ahmedabad', 'Gujarat', 'India'),
            ('Jyoti Prasad', 'jyoti@example.com', 'Patna', 'Bihar', 'India'),
            ('Rohit Sharma', 'rohit@example.com', 'Nagpur', 'Maharashtra', 'India'),
            ('Sunita Rao', 'sunita@example.com', 'Visakhapatnam', 'Andhra Pradesh', 'India'),
            ('Vivek Oberoi', 'vivek@example.com', 'Bangalore', 'Karnataka', 'India'),
            ('Pooja Hegde', 'pooja@example.com', 'Mangalore', 'Karnataka', 'India'),
            ('Divya Dutta', 'divya@example.com', 'Ludhiana', 'Punjab', 'India'),
            ('Harbhajan Singh', 'harbhajan@example.com', 'Jalandhar', 'Punjab', 'India'),
            ('Gaurav Taneja', 'gaurav@example.com', 'Kanpur', 'Uttar Pradesh', 'India'),
            ('Surbhi Jyoti', 'surbhi@example.com', 'Jalandhar', 'Punjab', 'India'),
            ('Kunal Khemu', 'kunal@example.com', 'Srinagar', 'Jammu & Kashmir', 'India'),
            ('Shreya Ghoshal', 'shreya@example.com', 'Kolkata', 'West Bengal', 'India'),
            ('Jaspreet Bumrah', 'jaspreet@example.com', 'Ahmedabad', 'Gujarat', 'India')
        ]

        print("Inserting new customers...")
        for name, email, city, state, country in new_customers:
            cursor.execute(
                "INSERT INTO customers (name, email, city, state, country) VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE city=%s, state=%s, country=%s;",
                (name, email, city, state, country, city, state, country)
            )

        # 2. Insert new products
        new_products = [
            ('Smart Watch Series 5', 'Electronics', 5499.00, 120),
            ('Wireless Charging Pad', 'Electronics', 1199.00, 250),
            ('Classic Leather Wallet', 'Accessories', 1499.00, 180),
            ('Anti-Theft Travel Backpack', 'Travel', 2499.00, 90),
            ('Aviator Sunglasses Classic', 'Accessories', 1899.00, 150),
            ('Ceramic Coffee Mug Set', 'Kitchen', 799.00, 300),
            ('Dual-Sided Desk Pad', 'Office', 999.00, 220),
            ('Ergonomic Office Chair', 'Furniture', 12499.00, 40),
            ('Classic Hardcover Notebook', 'Stationery', 499.00, 500),
            ('Premium Resistance Bands Set', 'Fitness', 899.00, 350)
        ]

        print("Inserting new products...")
        for name, cat, price, qty in new_products:
            cursor.execute(
                "INSERT INTO products (name, category, unit_price, stock_qty) VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE unit_price=%s, stock_qty=%s;",
                (name, cat, price, qty, price, qty)
            )

        connection.commit()

        # 3. Retrieve all customers and products to construct orders
        cursor.execute("SELECT customer_id FROM customers;")
        customers_list = [row['customer_id'] for row in cursor.fetchall()]

        cursor.execute("SELECT product_id, unit_price FROM products;")
        products_list = {row['product_id']: float(row['unit_price']) for row in cursor.fetchall()}

        # 4. Generate 50 new orders
        print("Generating 50 new orders...")
        statuses = ['completed', 'completed', 'completed', 'completed', 'pending', 'cancelled', 'refunded']
        
        # Start from Jan 1, 2026 to Jul 15, 2026
        start_date = datetime(2026, 1, 1)
        
        for i in range(50):
            cust_id = random.choice(customers_list)
            # Add random days
            days_to_add = random.randint(0, 195)
            hours_to_add = random.randint(8, 20)
            minutes_to_add = random.randint(0, 59)
            order_date = start_date + timedelta(days=days_to_add, hours=hours_to_add, minutes=minutes_to_add)
            status = random.choice(statuses)
            
            # Temporary insert with 0 total (we will calculate it and update)
            cursor.execute(
                "INSERT INTO orders (customer_id, order_date, status, order_total) VALUES (%s, %s, %s, 0.00);",
                (cust_id, order_date.strftime('%Y-%m-%d %H:%M:%S'), status)
            )
            order_id = cursor.lastrowid
            
            # Add items to order
            num_items = random.randint(1, 4)
            chosen_products = random.sample(list(products_list.keys()), num_items)
            order_total = 0.0
            
            for prod_id in chosen_products:
                qty = random.randint(1, 3)
                price = products_list[prod_id]
                item_total = qty * price
                order_total += item_total
                
                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s);",
                    (order_id, prod_id, qty, price)
                )
                
            # Update order total
            cursor.execute(
                "UPDATE orders SET order_total = %s WHERE order_id = %s;",
                (order_total, order_id)
            )

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        connection.commit()
        print("Successfully inserted 20 customers, 10 products, and 50 diverse orders with order items!")

finally:
    connection.close()
