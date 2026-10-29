# Ảnh chạy pipeline ETL + dashboard cho luồng L6
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 API_HOST=0.0.0.0 API_PORT=8000
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Nạp kho (chạy lại không nhân đôi) rồi mở dashboard
CMD ["sh", "-c", "python -m src.pipeline && python -m src.serve.app"]
