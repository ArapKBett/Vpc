FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y \
    build-essential libssl-dev libffi-dev \
    && pip install -r requirements.txt

EXPOSE 8080
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers", "4"]
