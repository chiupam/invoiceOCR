FROM python:3.9-slim

WORKDIR /app

COPY . .
RUN pip3 install --no-cache-dir -r requirements.txt

RUN mkdir -p data/output data/logs app/static/uploads

ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1
# 默认生产环境，可通过 docker-compose 覆盖
ENV APP_ENV=production

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/')" || exit 1

CMD ["python3", "run.py"]
