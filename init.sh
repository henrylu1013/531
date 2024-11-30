#!/bin/bash

# Wait for database to be ready
sleep 5

# Initialize database
python -c "from app import init_db; init_db()"

# Start Flask application
flask run --host=0.0.0.0 