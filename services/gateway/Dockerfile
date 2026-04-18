FROM python:3.12-slim
WORKDIR /app
COPY shared /app/shared
COPY services/gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY services/gateway /app/services/gateway
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
