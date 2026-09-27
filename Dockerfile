FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN SECRET_KEY=build-only python manage.py compile_translations \
    && SECRET_KEY=build-only python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --timeout 60 --access-logfile -"]
