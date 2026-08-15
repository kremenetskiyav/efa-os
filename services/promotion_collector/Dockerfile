FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir psycopg2-binary
COPY . .
CMD ["python", "server.py"]
