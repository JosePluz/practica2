import os
import sqlite3
import datetime
from flask import Flask, g, request, jsonify
from flask_cors import CORS

DB_PATH = "catalog.db"
API_KEY = os.environ.get("API_KEY", "devkey")

app = Flask(__name__)
CORS(app)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL
            )
        ''')
        conn.commit()


init_db()


@app.before_request
def require_apikey():
    if request.endpoint != 'health':
        key = request.headers.get("X-API-KEY")
        if key != API_KEY:
            return jsonify({"error": "unauthorized"}), 401


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "time": datetime.datetime.now().isoformat()
    })


@app.route('/products', methods=['POST'])
def create_product():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    if not all(field in data for field in ("name", "price", "stock")):
        return jsonify({"error": "name, price, and stock are required"}), 400

    name = data.get("name")
    price = data.get("price")
    stock = data.get("stock")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name must be a non-empty string"}), 400
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return jsonify({"error": "price must be a number"}), 400
    if isinstance(stock, bool) or not isinstance(stock, int):
        return jsonify({"error": "stock must be an integer"}), 400

    cursor = get_db().execute(
        "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
        (name.strip(), price, stock),
    )
    get_db().commit()
    product_id = cursor.lastrowid

    return jsonify({
        "id": product_id,
        "name": name.strip(),
        "price": price,
        "stock": stock
    }), 201


@app.route('/products', methods=['GET'])
def get_products():
    rows = get_db().execute("SELECT * FROM products").fetchall()
    products = [dict(row) for row in rows]
    return jsonify(products)

@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    row = get_db().execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))


@app.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "JSON object with product fields required"}), 400

    allowed_fields = {"name", "price", "stock"}
    if not set(data).issubset(allowed_fields):
        return jsonify({"error": "only name, price, and stock can be updated"}), 400
    if "name" in data and (not isinstance(data["name"], str) or not data["name"].strip()):
        return jsonify({"error": "name must be a non-empty string"}), 400
    if "price" in data and (
        isinstance(data["price"], bool) or not isinstance(data["price"], (int, float))
    ):
        return jsonify({"error": "price must be a number"}), 400
    if "stock" in data and (
        isinstance(data["stock"], bool) or not isinstance(data["stock"], int)
    ):
        return jsonify({"error": "stock must be an integer"}), 400

    if "name" in data:
        data["name"] = data["name"].strip()
    assignments = ", ".join(f"{field} = ?" for field in data)
    cursor = get_db().execute(
        f"UPDATE products SET {assignments} WHERE id = ?",
        (*data.values(), product_id),
    )
    if cursor.rowcount == 0:
        return jsonify({"error": "not found"}), 404
    get_db().commit()

    row = get_db().execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    return jsonify(dict(row))


@app.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    cursor = get_db().execute(
        "DELETE FROM products WHERE id = ?", (product_id,)
    )
    if cursor.rowcount == 0:
        return jsonify({"error": "not found"}), 404
    get_db().commit()

    return jsonify({"deleted": 1})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080)