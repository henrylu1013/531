#!/bin/sh

# Wait for database to be ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "postgres" -d "chatdb" -c '\q'; do
  echo "Postgres is unavailable - sleeping"
  sleep 1
done

echo "Postgres is up - initializing database"

# Remove existing migrations directory if it exists
rm -rf migrations/

# Initialize fresh migrations
flask db init

# Create a new migration
flask db migrate -m "initial migration"

# Apply the migration
flask db upgrade

# Start the application
echo "Starting Flask application..."
exec flask run --host=0.0.0.0 