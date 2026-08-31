# Phase 6: fine-tune a damage-severity image classifier
# Paste into a Databricks notebook (Python). Each "# COMMAND ----------" marks
# a separate cell if you import this file directly as a notebook instead.

# COMMAND ----------
# Installed via subprocess (not %pip + dbutils.library.restartPython()) —
# on Serverless compute, that combination double-restarts the Python
# environment and the installed packages don't survive to the next cell.
import subprocess
import sys

subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "torch", "torchvision", "--quiet"]
)

import importlib

importlib.invalidate_caches()

import io

import mlflow
import mlflow.pytorch
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

LABEL_MAP = {"ok": 0, "minor": 1, "major": 2}
INV_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}

df = spark.sql(
    "SELECT image_name, label, content FROM smart_claims_dev.02_silver.training_images"
).toPandas()
df = df[df["label"].isin(LABEL_MAP.keys())].reset_index(drop=True)
df["label_id"] = df["label"].map(LABEL_MAP)
print(f"Loaded {len(df)} training images. Label counts:\n{df['label'].value_counts()}")

# COMMAND ----------
transform = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


class ClaimImageDataset(Dataset):
    def __init__(self, df, transform):
        self.df = df
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img = Image.open(io.BytesIO(row["content"])).convert("RGB")
        return self.transform(img), row["label_id"]


dataset = ClaimImageDataset(df, transform)
loader = DataLoader(dataset, batch_size=8, shuffle=True)

# COMMAND ----------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Training on: {device}")

model = models.mobilenet_v2(weights="IMAGENET1K_V1")
for param in model.features.parameters():
    param.requires_grad = False  # freeze the pretrained "vision" part
model.classifier[1] = nn.Linear(model.last_channel, len(LABEL_MAP))
model = model.to(device)

optimizer = torch.optim.Adam(model.classifier.parameters(), lr=1e-3)
criterion = nn.CrossEntropyLoss()

mlflow.set_registry_uri("databricks-uc")
with mlflow.start_run(run_name="damage_classifier") as run:
    model.train()
    epochs = 15
    for epoch in range(epochs):
        total_loss, correct = 0.0, 0
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            correct += (outputs.argmax(1) == labels).sum().item()
        acc = correct / len(dataset)
        mlflow.log_metric("train_loss", total_loss, step=epoch)
        mlflow.log_metric("train_accuracy", acc, step=epoch)
        print(f"Epoch {epoch + 1}/{epochs} - loss: {total_loss:.4f} - accuracy: {acc:.2%}")

    # Unity Catalog requires a signature (input/output shape) on registration
    sample_images, _ = next(iter(loader))
    sample_images = sample_images.to(device)
    model.eval()
    with torch.no_grad():
        sample_output = model(sample_images)
    signature = mlflow.models.infer_signature(
        sample_images.cpu().numpy(), sample_output.cpu().numpy()
    )
    model.train()

    mlflow.pytorch.log_model(
        model,
        artifact_path="model",
        registered_model_name="smart_claims_dev.03_gold.claims_damage_classifier",
        signature=signature,
        input_example=sample_images.cpu().numpy(),
    )

print("Training complete. Run ID:", run.info.run_id)

# COMMAND ----------
# Apply the trained model to the real claim photos
model.eval()
claims_df = spark.sql(
    "SELECT image_name, content FROM smart_claims_dev.02_silver.claim_images"
).toPandas()

predictions = []
with torch.no_grad():
    for _, row in claims_df.iterrows():
        img = Image.open(io.BytesIO(row["content"])).convert("RGB")
        img_tensor = transform(img).unsqueeze(0).to(device)
        pred_id = model(img_tensor).argmax(1).item()
        predictions.append(
            {"image_name": row["image_name"], "predicted_severity": INV_LABEL_MAP[pred_id]}
        )

pred_df = pd.DataFrame(predictions)
spark.createDataFrame(pred_df).write.mode("overwrite").saveAsTable(
    "smart_claims_dev.03_gold.claims_damage_level"
)
display(spark.sql("SELECT * FROM smart_claims_dev.03_gold.claims_damage_level"))
