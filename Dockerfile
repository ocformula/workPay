# ============================================================
# Stage 1: Build React frontend
# ============================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: Flask — API + static file serving
# ============================================================
FROM python:3.9-slim AS flask-runtime
WORKDIR /app
COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./
# Copy React build output into Flask static folder
COPY --from=frontend-builder /app/dist ./static/frontend
RUN mkdir -p /data
ENV FLASK_APP=app.py
EXPOSE 8888
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=8888"]
