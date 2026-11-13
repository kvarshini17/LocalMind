"""
download_model.py
=================
Fetches the PDF embedding model so the app can run offline. Run this once
while connected to the internet:

    python download_model.py
"""

import os

os.environ["HF_HUB_OFFLINE"] = "0"  # the app itself always runs offline
os.environ["TRANSFORMERS_OFFLINE"] = "0"

from sentence_transformers import SentenceTransformer

from utils.constants import EMBEDDING_MODEL

SentenceTransformer(EMBEDDING_MODEL)
print(f"'{EMBEDDING_MODEL}' is ready. The app can now run offline.")
