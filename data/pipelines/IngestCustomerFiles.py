import duckdb
from duckdb.experimental.spark.sql import SparkSession as session
from duckdb.experimental.spark.sql.functions import lit, col
import os

#Open duckdb connection
con = duckdb.connect('my_database.db')

#Initialize DuckDB-backed Spark session
spark = session.builder.config('duckdb.database', 'my_database.db').getOrCreate()

#File/Folder paths of dataset.
salesdirectory = f'C:/Users/hlu/Documents/duckdb/Sales'
customerdirectory = f'C:/Users/hlu/Documents/duckdb/Customers/CUSTOMER_DIM.csv'
productdirectory = f'C:/Users/hlu/Documents/duckdb/Products/product_category.csv'

#Sales Folder has multiple csv files, it stores all the files into an array.
csv_files = [f for f in os.listdir(salesdirectory) if f.endswith('.csv')]

#this joins all the csv files into a temp table.
union_query = "\nUNION ALL\n".join(
    [f"SELECT * FROM read_csv('{os.path.join(salesdirectory, file)}', delim='`')" for file in csv_files]
)


flat_query = f"""
    SELECT 	NET_SALES_USD_BUDGET,
    NET_QTY_EACH,
     ACTIVITY_DATE,
      TRIM(SUBSTR(CUSTOMER_NAME, INSTR(CUSTOMER_NAME, ' - ') + 3)) AS CUSTOMER_COMPANY_NAME,
      BACKEND_NAME CUSTOMER_PERSON_NAME,
      ADDRESS CUSTOMER_ADDRESS,
      CITY CUSTOMER_CITY,
      COUNTRY CUSTOMER_COUNTRY,
      STATE_PROV CUSTOMER_STATE,
      MEMBER_INFO_TYPE CUSTOMER_MEMBER_TYPE,
      ITEM AS ITEM_NUMBER,
      ITEM_DESCRIPTION,
      PRODUCT_TYPE,
      BACKEND_MARKET_SEGMENT_SE PRODUCT_CATEGORY,
      1999 AS YEAR,
      '' AS QUARTER
    FROM (
        {union_query}
    ) AS unioned_files
    JOIN read_csv('{customerdirectory}', delim=',',ignore_errors=true) AS customer_dim
    ON unioned_files.DIR_CUSTOMER_COMPANY_KEY = customer_dim.CUSTOMER_COMPANY_KEY
        JOIN read_csv_auto('{productdirectory}',delim=',',ignore_errors=true)  AS product_dim
    ON unioned_files.ITEM_COMPANY_KEY = product_dim.ITEM_COMPANY_KEY
    WHERE 
        CUSTOMER_NAME NOT LIKE '%??%' 
        AND STATE_PROV NOT LIKE '%?%' 
        AND CITY NOT LIKE '%?%'
"""

#Create a table in Spark SQL to store the flattened query results
spark.sql(f"CREATE TABLE CUSTOMER_ORDERS as {flat_query}")


spark.sql(f"""
    UPDATE CUSTOMER_ORDERS
    SET ACTIVITY_DATE = STRFTIME(CAST(ACTIVITY_DATE AS DATE), '%m/%d/%Y')
    WHERE ACTIVITY_DATE LIKE '%-%'
""")

#Update activity dates and extract year and quarter
spark.sql(f"""
    UPDATE CUSTOMER_ORDERS
    SET YEAR = EXTRACT(YEAR FROM STRPTIME(ACTIVITY_DATE, '%m/%d/%Y')),  QUARTER =  EXTRACT(QUARTER FROM STRPTIME(ACTIVITY_DATE, '%m/%d/%Y'))
""")

# Aggregate data for customer order summaries
new_results_df = spark.sql(f"""
        SELECT 
        SUM(NET_SALES_USD_BUDGET) TOTAL_ORDER_AMOUNT,  
        AVG(NET_SALES_USD_BUDGET) AVERAGE_ORDER_AMOUNT,
        SUM(NET_QTY_EACH) TOTAL_QTY_EACH,
        AVG(NET_QTY_EACH) AVERAGE_QTY_EACH,
        CUSTOMER_COMPANY_NAME CUSTOMER_NAME,
        CUSTOMER_CITY,
        CUSTOMER_STATE,
        CUSTOMER_COUNTRY
        CUSTOMER_MEMBER_TYPE,
        COUNT(*) AS ORDER_FREQUENCY,
         YEAR,
        QUARTER,
        SUM(CASE WHEN PRODUCT_CATEGORY = 'Infusion' THEN 1 ELSE 0 END) AS INFUSION_COUNT,
       SUM(CASE WHEN PRODUCT_CATEGORY = 'Infusion_Systems' THEN 1 ELSE 0 END) AS INFUSION_SYSTEMS_COUNT,
       SUM(CASE WHEN PRODUCT_CATEGORY = 'Vascular Access' THEN 1 ELSE 0 END) AS VASCULAR_ACCESS_COUNT,
       SUM(CASE WHEN PRODUCT_CATEGORY = 'Oncology' THEN 1 ELSE 0 END) AS ONCOLOGY_COUNT,
         SUM(CASE WHEN PRODUCT_CATEGORY = 'Other' THEN 1 ELSE 0 END) AS OTHER_COUNT,                    
          SUM(CASE WHEN PRODUCT_CATEGORY = 'Veterinary' THEN 1 ELSE 0 END) AS VETERINARY_COUNT,      
      SUM(CASE WHEN PRODUCT_CATEGORY = 'Service' THEN 1 ELSE 0 END) AS SERVICE_COUNT,
       SUM(CASE WHEN PRODUCT_CATEGORY = 'Critical Care' THEN 1 ELSE 0 END) AS CRITICAL_CARE_COUNT,                    
          SUM(CASE WHEN PRODUCT_CATEGORY = 'Respiratory' THEN 1 ELSE 0 END) AS RESPIRATORY_COUNT, 
      SUM(CASE WHEN PRODUCT_CATEGORY = 'Solutions' THEN 1 ELSE 0 END) AS SOLUTIONS_COUNT,     
      SUM(CASE WHEN PRODUCT_CATEGORY = 'N/A' THEN 1 ELSE 0 END) AS NA_COUNT,
                                                                    
    FROM CUSTOMER_ORDERS
    GROUP BY 
        CUSTOMER_COMPANY_NAME,
        YEAR,
        QUARTER,
        CUSTOMER_CITY,
        CUSTOMER_STATE,
        CUSTOMER_MEMBER_TYPE,
        CUSTOMER_COUNTRY
""")


#register spark dataframe to duck db temp table.
con.register('my_temp_table', new_results_df.toPandas())


#drop and recreate customers_order_amt table
try:
    con.execute("DROP TABLE customers_orders_amt")
except:
    pass

con.execute("CREATE TABLE customers_orders_amt AS SELECT * FROM my_temp_table")
con.close()