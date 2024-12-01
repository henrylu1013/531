import duckdb
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA  


#Open duckdb connection
con = duckdb.connect('my_database.db')

#Select from customers_orders_amt to Pandas Dataframe
df = con.execute('select * from customers_orders_amt').df()

#Scaling each feature to range [0,1]
scaler = MinMaxScaler()

#Create scalar 1
X_scaled_1 = scaler.fit_transform(df[['TOTAL_ORDER_AMOUNT', 'AVERAGE_ORDER_AMOUNT']])

#Predicting
kmeans_1 = KMeans(n_clusters=3, init='k-means++', random_state=42)
df['Categorized_1'] = kmeans_1.fit_predict(X_scaled_1)

#Mapping the categories it produced for scalar 1.
cluster_mapping_1 = {0: 'Low-End Sales Customer', 1: 'Medium Sales Customer', 2: 'High-Valued Sales Customer'}
df['Categorized_1_Label'] = df['Categorized_1'].map(cluster_mapping_1)

#Create scalar 2
X_scaled_2 = scaler.fit_transform(df[['TOTAL_QTY_EACH', 'AVERAGE_QTY_EACH']])

#Predicting
kmeans_2 = KMeans(n_clusters=3, init='k-means++', random_state=42)
df['Categorized2'] = kmeans_2.fit_predict(X_scaled_2)

#Mapping the categories it produced for scalar 2.
cluster_mapping_2 = {0: 'Low-End QTY Customer', 1: 'Medium QTY Customer', 2: 'High QTY Customer'}
df['Categorized_2_Label'] = df['Categorized2'].map(cluster_mapping_2)


# Visualize the First Categorization
plt.figure(figsize=(10, 5))
for category in range(kmeans_1.n_clusters):  # Iterate over the clusters
    cluster_points = X_scaled_1[df['Categorized_1'] == category]
    plt.scatter(
        cluster_points[:, 0],
        cluster_points[:, 1],
        label=f'Categorized_1 {category}'
    )

centroids_1 = kmeans_1.cluster_centers_
plt.scatter(centroids_1[:, 0], centroids_1[:, 1], s=300, c='red', marker='X', label='Centroids_1')
plt.xlabel('Total Order Amount (Scaled)')
plt.ylabel('Average Order Amount (Scaled)')
plt.title('Customer Clusters for Categorization 1')
plt.legend()
plt.show()

# Visualize the Second Categorization
plt.figure(figsize=(10, 5))
for category in range(kmeans_2.n_clusters):  # Iterate over the clusters
    cluster_points = X_scaled_2[df['Categorized2'] == category]
    plt.scatter(
        cluster_points[:, 0],
        cluster_points[:, 1],
        label=f'Categorized2 {category}'
    )

centroids_2 = kmeans_2.cluster_centers_
plt.scatter(centroids_2[:, 0], centroids_2[:, 1], s=300, c='blue', marker='X', label='Centroids_2')
plt.xlabel('TOTAL_QTY_EACH (Scaled)')
plt.ylabel('AVERAGE_QTY_EACH (Scaled)')
plt.title('Customer Clusters for Categorization 2')
plt.legend()
plt.show()

#Drop the Numeric categorized columns.
df.drop(columns=['Categorized2','Categorized_1' ], inplace=True)

#export to csv
df.to_csv('clustered_customers.csv', index=False)

con.close()