import torch, torch.nn as nn
from torch.functional import F
from torch.utils.data import Dataset
from torchvision import transforms


class NTXentCrossEntropyLoss(nn.Module):
    def __init__(self, temperature=0.5):
        super().__init__()
        self.temperature = temperature

    def forward(self, z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        assert z1.shape == z2.shape, f"expect two tensor has same shape, but got z1.shape: {z1.shape}, z2.shape: {z2.shape}."
        N, D = z1.shape
        Z = torch.zeros((2 * N, D), device=z1.device, dtype=torch.float32)
        Z[::2, :], Z[1::2, :] = z1, z2
        Z = F.normalize(Z, dim=1)
        sim_mat = torch.exp(torch.mm(Z, Z.T) / self.temperature)
        loss = 0
        for i in range(N):
            loss += self._loss(sim_mat, 2 * i, 2 * i + 1) + self._loss(
                sim_mat, 2 * i + 1, 2 * i
            )
        return loss / (2 * N)

    def _loss(self, sim_mat: torch.Tensor, i: int, j: int):
        return -torch.log(
            sim_mat[i][j] / (torch.sum(sim_mat[i, :]) - sim_mat[i, i] + 1e-8)
        )


class SimCLRModel(nn.Module):

    def __init__(self, encoder: nn.Module, projection_dim: int):
        """
        SimCLR model.
        """
        super(SimCLRModel, self).__init__()
        self.encoder = encoder
        self.projection_head = nn.Sequential(
            nn.Linear(512, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, projection_dim),
        )

    def forward(self, inputs: torch.Tensor):
        features = self.encoder(inputs)
        projections = self.projection_head(features)
        return features, projections


class Classifier(nn.Module):
    def __init__(self, encoder: nn.Module, out_features: int):
        super(Classifier, self).__init__()
        self.encodr = encoder
        self.classification_head = nn.Sequential(nn.Linear(512, out_features))

    def forward(self, inputs: torch.Tensor):
        with torch.no_grad():
            features = self.encodr(inputs)
        out = self.classification_head(features)
        return F.softmax(out, dim=1)


class SimCLRDataset(Dataset):
    def __init__(self, dataset, transform):
        self.dataset = dataset
        self.transform = transform

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        features, labels = self.dataset[index]
        image_pil = transforms.ToPILImage()(features)
        view_1 = self.transform(image_pil)
        view_2 = self.transform(image_pil)
        return view_1, view_2, labels
