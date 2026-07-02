"""Graph Neural Network foundation for zone‑based traffic prediction.

This module provides a 2‑layer Graph Convolutional Network (GCN) that
captures spatial dependencies between adjacent zones. The GNN is an
experimental parallel path to XGBoost — it does not replace it.
"""

import numpy as np
import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv
from torch_geometric.data import Data
from typing import Dict, Tuple


class GCN(torch.nn.Module):
    """2‑layer GCN for regression on zone graphs."""

    def __init__(self, in_channels: int, hidden_channels: int, out_channels: int):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, out_channels)

    def forward(self, data: Data) -> torch.Tensor:
        x, edge_index = data.x, data.edge_index
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.conv2(x, edge_index)
        return torch.sigmoid(x)   # output in [0,1]


def build_zone_graph(zone_adjacency: Dict[str, list]) -> Data:
    """Build a PyTorch Geometric Data object from ZONE_ADJACENCY.

    Creates an undirected graph with self‑loops. Nodes are indexed
    in the order they appear in the keys of zone_adjacency (sorted).
    """
    zones = sorted(zone_adjacency.keys())          # e.g. ['Zone_1', ..., 'Zone_5']
    zone_to_idx = {z: i for i, z in enumerate(zones)}

    edge_list = []
    for z, neighbors in zone_adjacency.items():
        u = zone_to_idx[z]
        for n in neighbors:
            if n in zone_to_idx:
                v = zone_to_idx[n]
                edge_list.append([u, v])   # undirected – will add reverse later

    # Add reverse edges to make it undirected
    undirected_edges = edge_list + [[v, u] for u, v in edge_list]

    # Remove duplicates (if any)
    unique_edges = list(set(tuple(e) for e in undirected_edges))
    edge_index = torch.tensor(unique_edges, dtype=torch.long).t().contiguous()

    # Add self‑loops (standard for GCN)
    num_nodes = len(zones)
    self_loops = torch.tensor([[i, i] for i in range(num_nodes)], dtype=torch.long).t()
    edge_index = torch.cat([edge_index, self_loops], dim=1)

    return Data(edge_index=edge_index, num_nodes=num_nodes)


# In src/gnn_model.py

def reshape_to_graph_snapshots(X: np.ndarray, y: np.ndarray,
                               num_zones: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """Reshape flat feature matrix and target into graph snapshots.

    Assumes rows are ordered by timestamp and then by zone (all zones
    appear for each timestamp). If the total number of samples is not
    a multiple of num_zones, the extra rows are trimmed from the end.
    """
    num_samples = X.shape[0]
    # Trim to largest multiple of num_zones
    trim_to = (num_samples // num_zones) * num_zones
    if trim_to < num_samples:
        X = X[:trim_to]
        y = y[:trim_to]
        num_samples = trim_to

    X_reshaped = X.reshape(num_samples // num_zones, num_zones, -1)
    y_reshaped = y.reshape(num_samples // num_zones, num_zones)
    return X_reshaped, y_reshaped

def train_gnn(X_node_features: np.ndarray,
              y: np.ndarray,
              zone_graph: Data,
              epochs: int = 50) -> GCN:
    """Train a GCN on graph snapshots.

    Parameters
    ----------
    X_node_features : (num_timesteps, num_zones, num_features)
    y               : (num_timesteps, num_zones)
    zone_graph      : PyG Data object with edge_index, num_nodes
    epochs          : number of training epochs

    Returns
    -------
    trained GCN model
    """
    edge_index = zone_graph.edge_index
    num_timesteps, num_nodes, num_features = X_node_features.shape

    # Build list of snapshot Data objects
    snapshots = []
    for t in range(num_timesteps):
        data = Data(
            x=torch.tensor(X_node_features[t], dtype=torch.float),
            y=torch.tensor(y[t], dtype=torch.float).view(-1, 1),
            edge_index=edge_index
        )
        snapshots.append(data)

    # Model
    hidden_channels = 16
    model = GCN(num_features, hidden_channels, 1)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    criterion = torch.nn.MSELoss()

    # Training loop
    for epoch in range(epochs):
        # Shuffle snapshots
        indices = np.random.permutation(num_timesteps)
        total_loss = 0.0
        for idx in indices:
            data = snapshots[idx]
            optimizer.zero_grad()
            out = model(data)
            loss = criterion(out, data.y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % 10 == 0:
            print(f"GNN epoch {epoch+1}/{epochs} — loss: {total_loss/num_timesteps:.4f}")

    return model


def predict_gnn(model: GCN,
                X_node_features: np.ndarray,
                zone_graph: Data) -> np.ndarray:
    """Run inference with the GCN for all snapshots.

    Returns predictions of shape (num_timesteps, num_zones).
    """
    edge_index = zone_graph.edge_index
    model.eval()
    preds = []
    with torch.no_grad():
        for t in range(X_node_features.shape[0]):
            data = Data(
                x=torch.tensor(X_node_features[t], dtype=torch.float),
                edge_index=edge_index
            )
            out = model(data)
            preds.append(out.numpy().flatten())
    return np.array(preds)
