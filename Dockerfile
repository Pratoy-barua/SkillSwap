FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system skillswap && adduser --system --ingroup skillswap skillswap

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p static/uploads/public private_uploads/verification \
    && chown -R skillswap:skillswap /app

USER skillswap

EXPOSE 5000

CMD ["sh", "-c", "flask --app app init-db && gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 60 wsgi:app"]
