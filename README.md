# Set up instructions
## Set up your dotenv
1. create a .env file in the root directory
2. add your anthropic api key to the .env file

## Initialize project
`docker compose up --build`

## Initialize database
`python load_data.py`

## Checkout website
`localhost:5001`

# Files
## App 
App is built with Flask and Langchain. It uses Anthropic Claude 3.0 sonnet model as the LLM. 

- `app.py` is the main file that runs the flask app.
- `Dockerfile` is used to containerize the flask app.
- `entrypoint.sh` is used to initialize the database and run the flask app.
- `load_data.py` is used to load the data into the database.

## Frontend (Vue.js)
Frontend is built with Vue.js

- `static/style.css` is used to style the frontend.
- `templates/index.html` is the main template that is used to render the frontend.

## Data
Data pipeline uses duckdb SparkSQL API to load, join, and aggregate the data.
After aggregation, the data is clustered using KMeans clustering algorithm.

- `data/static/schema.json` is the schema of the postgreSQL table.
- `data/static/clustered_customer_data.json` is the clustered customer data.
- `data/pipelines/ClassifyModel.py` is the script that is used to classify the customer data using KMeans clustering algorithm.
- `data/pipelines/IngestCustomerFiles.py` is the script that is used to ingest the customer data using duckdb SparkSQL API.
