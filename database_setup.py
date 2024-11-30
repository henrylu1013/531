from flask_sqlalchemy import SQLAlchemy
import json

db = SQLAlchemy()

class CustomerData(db.Model):
    __tablename__ = 'customer_data'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(255), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    quarter = db.Column(db.String(2), nullable=False)
    total_order_amount = db.Column(db.Float, nullable=False)
    average_order_amount = db.Column(db.Float, nullable=False)
    order_frequency = db.Column(db.Integer, nullable=False)
    categorized = db.Column(db.Integer, nullable=False)

def load_schema():
    with open('/app/data/static/schema.json', 'r') as f:
        return json.load(f)