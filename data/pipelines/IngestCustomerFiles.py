import duckdb
from duckdb.experimental.spark.sql import SparkSession as session
from duckdb.experimental.spark.sql.functions import lit, col

import os
spark = session.builder.getOrCreate()

salesdirectory = f'C:/Users/hlu/Documents/duckdb/Sales'
customerdirectory = f'C:/Users/hlu/Documents/duckdb/Customers/CUSTOMER_DIM.csv'
con = duckdb.connect('my_database.db')
csv_files = [f for f in os.listdir(salesdirectory) if f.endswith('.csv')]

union_query = "\nUNION ALL\n".join(
    [f"SELECT * FROM read_csv('{os.path.join(salesdirectory, file)}', delim='`')" for file in csv_files]
)
# duckdb.sql("""
#     SELECT sale.COMPANY_ID,ITEM_COMPANY_KEY,	DIR_CUSTOMER_COMPANY_KEY,	END_CUSTOMER_COMPANY_KEY,	ACTIVITY_DATE,NET_QTY_EACH,	NET_SALES_USD_BUDGET,BACKEND_MARKET_SEGMENT_SE,
#            ADDRESS_NAME,ADDRESS,CITY, POSTAL_ZIP, STATE_PROV, COUNTRY
#   FROM read_csv('InDirectSaleApr2023.csv', delim='`', header=True) as sale
#                          join read_csv('CUSTOMER_DIM.csv', delim=',', header=True, ignore_errors = true) cust
#                         on sale.DIR_CUSTOMER_COMPANY_KEY = cust.CUSTOMER_COMPANY_KEY
# """).show()

# full_query = f"""
#     SELECT unioned_files.COMPANY_ID,ITEM_COMPANY_KEY,	DIR_CUSTOMER_COMPANY_KEY,	END_CUSTOMER_COMPANY_KEY,	ACTIVITY_DATE,NET_QTY_EACH,	NET_SALES_USD_BUDGET,BACKEND_MARKET_SEGMENT_SE,
#       ADDRESS_NAME,ADDRESS,CITY, POSTAL_ZIP, STATE_PROV, COUNTRY
#     FROM (
#         {union_query}
#     ) AS unioned_files
#     JOIN read_csv('{customerdirectory}', delim=',',ignore_errors=true) AS customer_dim
#     ON unioned_files.DIR_CUSTOMER_COMPANY_KEY = customer_dim.CUSTOMER_COMPANY_KEY
# """
full_query = f"""
    SELECT 	NET_SALES_USD_BUDGET,
     ACTIVITY_DATE,
      CUSTOMER_NAME
    FROM (
        {union_query}
    ) AS unioned_files
    JOIN read_csv('{customerdirectory}', delim=',',ignore_errors=true) AS customer_dim
    ON unioned_files.DIR_CUSTOMER_COMPANY_KEY = customer_dim.CUSTOMER_COMPANY_KEY
"""

results_df = duckdb.sql(full_query).fetchdf()

try:
    con.execute("DROP TABLE Temp_Stage")
except:
    ''
con.execute("CREATE TABLE Temp_Stage AS SELECT * FROM results_df")

con.execute(f"""
    UPDATE Temp_Stage
    SET ACTIVITY_DATE = STRFTIME(CAST(ACTIVITY_DATE AS DATE), '%m/%d/%Y')
    WHERE ACTIVITY_DATE LIKE '%-%'
""")
new_results_df = con.execute(f"""
    SELECT 
        NET_SALES_USD_BUDGET, 
        CUSTOMER_NAME,
        EXTRACT(YEAR FROM STRPTIME(ACTIVITY_DATE, '%m/%d/%Y')) AS YEAR,
        'Q' || EXTRACT(QUARTER FROM STRPTIME(ACTIVITY_DATE, '%m/%d/%Y')) AS QUARTER
    FROM Temp_Stage
""").fetchdf()


# 1. Calculate Total Order Amount per Customer
total_order_amount = new_results_df.groupby(['CUSTOMER_NAME','YEAR','QUARTER'])['NET_SALES_USD_BUDGET'].sum()

# 2. Calculate Average Order Amount per Customer
average_order_amount = new_results_df.groupby(['CUSTOMER_NAME','YEAR','QUARTER'])['NET_SALES_USD_BUDGET'].mean()

# 3. Calculate Order Frequency per Customer (number of orders per customer)
order_frequency = new_results_df.groupby(['CUSTOMER_NAME','YEAR','QUARTER']).size()

customer_summary = (
    total_order_amount.to_frame(name='TOTAL_ORDER_AMOUNT')
    .join(average_order_amount.rename('AVERAGE_ORDER_AMOUNT'))
    .join(order_frequency.rename('ORDER_FREQUENCY'))
    .reset_index()  # Reset index to make CUSTOMER_NAME a column
)
print(customer_summary)
try:
    con.execute("DROP TABLE customers_orders_amt")
except:
    ''
con.execute("CREATE TABLE customers_orders_amt AS SELECT * FROM customer_summary")

con.close()