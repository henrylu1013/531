import duckdb
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA  

con = duckdb.connect('my_database.db')

df = con.execute('select * from customers_orders_amt').df()
print(df)
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(df[['TOTAL_ORDER_AMOUNT', 'AVERAGE_ORDER_AMOUNT', 'ORDER_FREQUENCY']])  # Three features

# Fit K-Means with the chosen number of clusters
kmeans = KMeans(n_clusters=3, random_state=42)
df['Categorized'] = kmeans.fit_predict(X_scaled)

df.to_csv('clustered_customers.csv', index=False)

# Create a 3D scatter plot
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

# Plot each cluster with a different color
for Categorized in set(df['Categorized']):
    ax.scatter(
        X_scaled[df['Categorized'] == Categorized, 0],  # low end 
        X_scaled[df['Categorized'] == Categorized, 1],  # mid end
        X_scaled[df['Categorized'] == Categorized, 2],  # high end
        label=f'Categorized {Categorized}'
    )

# Plot centroids in 3D space
centroids = kmeans.cluster_centers_
ax.scatter(centroids[:, 0], centroids[:, 1], centroids[:, 2], s=300, c='red', marker='X', label='Centroids')

# Label the axes
ax.set_xlabel('Total Order Amount (Scaled)')
ax.set_ylabel('Average Order Amount (Scaled)')
ax.set_zlabel('Order Frequency (Scaled)')
ax.set_title('Customer Clusters in 3D Feature Space')
ax.legend()

# Show the plot
plt.show()
con.close()