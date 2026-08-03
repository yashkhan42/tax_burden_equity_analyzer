# One image that serves the Next.js site and the model API from a single
# origin. The site is a client-rendered SPA, so there is nothing for a Node
# process to do at request time: it is exported to static files at build time
# and handed to FastAPI. That removes the second service, the CORS grant, and
# the HTTPS/HTTP mixed-content edge between the two halves.
#
# Runs on anything that takes a Dockerfile. Listens on $PORT when the platform
# sets one (Render, Fly, Railway) and falls back to 7860 for Hugging Face
# Spaces, which expects that port by default.

# ---------------------------------------------------------------- web build
FROM node:22-bookworm-slim AS web

# The repo layout is reproduced rather than flattened: the `prebuild` hook runs
# scripts/sync-tokens.mjs, which reads ../design/tokens.json. That palette sits
# at the repo root because the Streamlit theme shares it, so the two surfaces
# cannot drift apart. Copying only frontend/ leaves the build looking for
# /design/tokens.json and failing.
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY design/ /build/design/
COPY frontend/ ./

# An empty base URL makes the browser request /api/v1/... relative to whatever
# host is serving the page. A real environment variable beats any committed
# .env file in Next.js, so this wins over the local development default.
ENV NEXT_PUBLIC_API_URL=""
RUN npm run build


# --------------------------------------------------------------- API runtime
FROM python:3.13-slim

# scikit-learn must match the version the forest was pickled with; the runtime
# raises ModelContractError rather than loading a subtly different model.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

# Only what the API actually reads at runtime. The 276 MB forest is *not*
# baked in -- it is fetched from the public GitHub Release on first boot and
# verified against the checksum in rf_metrics.json.
COPY backend/ ./backend/
COPY model_interface.py ./
COPY models/rf_metrics.json ./models/
COPY data/processed/freeze_manifest.json ./data/processed/
COPY data/processed/train.csv ./data/processed/
COPY data/processed/test.csv ./data/processed/

COPY --from=web /build/frontend/out ./frontend/out

# Hosts commonly run the container as a non-root user with no write access to
# /app, and the artifact has to land somewhere writable on first boot.
ENV TAX_MODEL_PATH=/tmp/rf_eff_rate.joblib
ENV PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
