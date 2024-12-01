from sqlalchemy import create_engine
import pandas as pd

def clean_column_name(col):
    # Remove leading/trailing spaces and special characters
    # Convert to lowercase and replace spaces with underscores
    return col.strip().lower().replace(' ', '_').replace('.', '').replace('"', '')

def load_customer_data(csv_path):
    try:
        # Read the CSV file, skipping the first row
        df = pd.read_csv(csv_path)
        
        # Clean up column names
        df.columns = [clean_column_name(col) for col in df.columns]
        
        # Print column names for debugging
        print("Columns after cleaning:", df.columns.tolist())
        
        # Create database connection
        database_url = 'postgresql://postgres:postgres@localhost:5432/chatdb'
        engine = create_engine(database_url)
        
        # Convert DataFrame to SQL
        df.to_sql(
            'customer_data', 
            engine, 
            if_exists='replace',  # Changed to 'replace' to avoid duplicate issues
            index=False,
            method='multi',
            chunksize=1000  # Process 1000 rows at a time
        )
        
        print(f"Successfully loaded {len(df)} rows into customer_data table")
                    
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        raise

if __name__ == "__main__":
    # Specify your CSV file path
    csv_path = "data/static/clustered_customers.csv"
    load_customer_data(csv_path)