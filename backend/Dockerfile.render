# Local dev uses conda (environment.yml) — this uses plain pip
# (requirements.render.txt) since every dependency has a pip wheel; conda
# there is for convenience (and to dodge Anaconda's ToS-gated channel), not
# a hard requirement.
FROM python:3.10-slim

WORKDIR /app

# opencv-python-headless still dlopens libGL/libglib at import time even
# though it never opens a window.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# torch/torchvision default to CUDA-bundled wheels (multi-GB of nvidia-*
# packages) even though this host has no GPU; the CPU wheel index avoids
# that entirely and cuts the image from ~9.4GB to a few hundred MB.
COPY requirements.render.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.render.txt

# The patchcore detector is instantiated eagerly at import time and pulls
# pretrained ResNet18 weights from download.pytorch.org — baking them into
# the image means container start doesn't depend on that host being
# reachable, and boots faster on every subsequent deploy/restart.
RUN python -c "import torchvision; from torchvision.models import ResNet18_Weights; torchvision.models.resnet18(weights=ResNet18_Weights.DEFAULT)"

COPY . .

# Regenerates the synthetic sample images/video this demo runs against —
# see scripts/generate_demo_assets.py's docstring. Nothing here is real
# product data; keeping it out of the image and generating fresh at build
# time is simpler than deciding what's safe to ship as binary assets.
RUN python scripts/generate_demo_assets.py

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
