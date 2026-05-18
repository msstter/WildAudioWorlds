import umap
from sklearn.preprocessing import StandardScaler
import numpy as np

class DimensionalityReducer:
    def __init__(self, n_neighbors=15, min_dist=0.1):
        # n_neighbors: Controls how UMAP balances local vs global structure.
        # min_dist: Controls how tightly packed the points are. 
        # Tweak these later to change the "look" of your 3D shapes!
        self.reducer = umap.UMAP(
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            n_components=3, # We want exactly X, Y, Z
            random_state=42 # Set a seed so the same audio makes the exact same shape
        )
        self.scaler = StandardScaler()

    def reduce_to_3d(self, feature_matrix):
        """
        Takes a high-dimensional feature matrix and reduces it to 3D.
        """
        # 1. Scale the data so all features have equal weight
        scaled_features = self.scaler.fit_transform(feature_matrix)

        # 2. Fit the UMAP model and transform the data into 3 dimensions
        print("Calculating UMAP embedding (this might take a few seconds)...")
        embedding_3d = self.reducer.fit_transform(scaled_features)

        return embedding_3d