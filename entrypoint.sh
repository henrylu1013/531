#!/bin/sh

# Wait for database to be ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "postgres" -d "chatdb" -c '\q'; do
  echo "Postgres is unavailable - sleeping"
  sleep 1
done

echo "Postgres is up - initializing database"

# Initialize fresh migrations
flask db init

# Start the application
echo "Starting Flask application..."
exec flask run --host=0.0.0.0 