# ---- Stage 1: Build React frontend ----
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.9-slim
WORKDIR /app

# Install deps
COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python source
COPY src/ ./

# Copy React build output into Flask static folder
COPY --from=frontend-builder /frontend/dist ./static/frontend

# Data directory (mounted at runtime)
RUN mkdir -p /data

EXPOSE 8888
ENV FLASK_APP=app.py
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8888"]
