import os
import json
import sqlite3
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, HTTPServer

DB_FILE = 'database.db'
UPLOAD_DIR = 'uploads'

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            category TEXT,
            price REAL,
            link TEXT,
            image TEXT,
            is_featured INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    
    # Pre-populate categories
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        cats = ["Beleza", "Casa & Decor", "Utilidades", "Moda"]
        for cat in cats:
            c.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
        conn.commit()

    # Pre-populate products
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        default_products = [
            ("Mini Umidificador Aromatizador Portátil", "Deixe seu quarto ou escritório com um cheirinho maravilhoso. Design de madeira sofisticado e com luzes LED RGB coloridas de fundo.", "Casa & Decor", 24.90, "https://shopee.com.br", "https://images.unsplash.com/photo-1519183071298-a2962feb14f4?auto=format&fit=crop&q=80&w=400", 1),
            ("Kit Pincéis de Maquiagem Profissional Pastel", "Estojo com 8 pincéis super macios nas cores pastéis. Ideal para blush, sombra e pó compacto.", "Beleza", 18.50, "https://shopee.com.br", "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&q=80&w=400", 0),
            ("Garrafa Térmica Motivacional 2 Litros", "Garrafa perfeita para levar à academia, com adesivos fofos em 2D/3D inclusos e marcações de horários para beber água.", "Utilidades", 32.00, "https://shopee.com.br", "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&q=80&w=400", 1)
        ]
        for p in default_products:
            c.execute("INSERT INTO products (title, description, category, price, link, image, is_featured) VALUES (?, ?, ?, ?, ?, ?, ?)", p)
        conn.commit()
    conn.close()

class DudaServerHandler(SimpleHTTPRequestHandler):
    def parse_multipart(self, content_length, boundary):
        body = self.rfile.read(content_length)
        parts = body.split(b'--' + boundary)
        fields = {}
        files = {}
        
        for part in parts:
            if not part or part == b'\r\n' or part == b'--\r\n' or part == b'--':
                continue
            
            # Split headers and body
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue
                
            headers_bytes = part[:header_end]
            body_bytes = part[header_end+4:]
            
            # Remove trailing \r\n
            if body_bytes.endswith(b'\r\n'):
                body_bytes = body_bytes[:-2]
                
            headers_str = headers_bytes.decode('utf-8', errors='ignore')
            
            disposition = ""
            for line in headers_str.split('\r\n'):
                if line.lower().startswith('content-disposition:'):
                    disposition = line
                    break
            
            if not disposition:
                continue
                
            name = ""
            filename = ""
            for token in disposition.split(';'):
                token = token.strip()
                if token.startswith('name='):
                    name = token.split('=')[1].strip('"')
                elif token.startswith('filename='):
                    filename = token.split('=')[1].strip('"')
            
            if filename:
                files[name] = {
                    'filename': filename,
                    'content': body_bytes
                }
            else:
                fields[name] = body_bytes.decode('utf-8', errors='ignore')
                
        return fields, files

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # API Routes
        if path == '/api/products':
            self.get_products()
        elif path == '/api/categories':
            self.get_categories()
        else:
            # Fallback to serving static files
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path == '/api/products':
            self.add_product()
        elif path == '/api/products/toggle-featured':
            self.toggle_featured()
        elif path == '/api/categories':
            self.add_category()
        elif path == '/api/login':
            self.admin_login()
        else:
            self.send_error(404, "Not Found")

    def do_DELETE(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        
        if path == '/api/products':
            prod_id = query.get('id', [None])[0]
            if prod_id:
                self.delete_product(prod_id)
            else:
                self.send_error(400, "Missing ID parameter")
        elif path == '/api/categories':
            cat_name = query.get('name', [None])[0]
            if cat_name:
                self.delete_category(cat_name)
            else:
                self.send_error(400, "Missing name parameter")
        else:
            self.send_error(404, "Not Found")

    # API Handlers
    def get_products(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT id, title, description, category, price, link, image, is_featured FROM products ORDER BY id DESC")
            rows = c.fetchall()
            products = []
            for row in rows:
                products.append({
                    'id': row[0],
                    'title': row[1],
                    'description': row[2],
                    'category': row[3],
                    'price': row[4],
                    'link': row[5],
                    'image': row[6],
                    'is_featured': row[7]
                })
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(products, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def get_categories(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT name FROM categories")
            rows = c.fetchall()
            categories = ["Todos"] + [row[0] for row in rows]
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(categories, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def add_product(self):
        try:
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_error(400, "Content-Type must be multipart/form-data")
                return
                
            boundary = content_type.split("boundary=")[1].encode()
            content_length = int(self.headers.get('Content-Length', 0))
            
            fields, files = self.parse_multipart(content_length, boundary)
            
            title = fields.get('title', '').strip()
            description = fields.get('description', '').strip()
            category = fields.get('category', '').strip()
            price = fields.get('price', '')
            link = fields.get('link', '').strip()
            image_url = fields.get('imageUrl', '').strip()
            is_featured = int(fields.get('isFeatured', '0'))
            
            if not title or not category or not link:
                self.send_error(400, "Missing required fields")
                return
                
            # Handle price
            try:
                price_val = float(price) if price else None
            except ValueError:
                price_val = None
                
            # Process uploaded file if present
            image_path = image_url
            if 'imageFile' in files and files['imageFile']['filename']:
                file_info = files['imageFile']
                ext = os.path.splitext(file_info['filename'])[1]
                filename = f"upload_{int(time.time())}{ext}"
                target_path = os.path.join(UPLOAD_DIR, filename)
                
                with open(target_path, 'wb') as f:
                    f.write(file_info['content'])
                    
                image_path = f"/uploads/{filename}"

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "INSERT INTO products (title, description, category, price, link, image, is_featured) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, description, category, price_val, link, image_path, is_featured)
            )
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def toggle_featured(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            prod_id = data.get('id')
            is_featured = int(data.get('is_featured', 0))
            
            if prod_id is None:
                self.send_error(400, "Missing product ID")
                return
                
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE products SET is_featured = ? WHERE id = ?", (is_featured, prod_id))
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def delete_product(self, prod_id):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # Optional: Delete uploaded file if it was stored locally
            c.execute("SELECT image FROM products WHERE id = ?", (prod_id,))
            row = c.fetchone()
            if row and row[0] and row[0].startswith('/uploads/'):
                file_rel_path = row[0].lstrip('/')
                if os.path.exists(file_rel_path):
                    try:
                        os.remove(file_rel_path)
                    except:
                        pass # Ignore delete failures
                        
            c.execute("DELETE FROM products WHERE id = ?", (prod_id,))
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def add_category(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            name = data.get('name', '').strip()
            if not name:
                self.send_error(400, "Missing name")
                return
                
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            try:
                c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                conn.commit()
                status = 'success'
            except sqlite3.IntegrityError:
                status = 'already_exists'
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': status}).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def delete_category(self, cat_name):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM categories WHERE name = ?", (cat_name,))
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def admin_login(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            
            password = data.get('password', '')
            if password == '1234':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))
            else:
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'unauthorized'}).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

def run(port=8080):
    init_db()
    server_address = ('', port)
    httpd = HTTPServer(server_address, DudaServerHandler)
    print(f"Servidor dos Achadinhos da Duda rodando na porta {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    run(port=port)
