# Gunicorn configuration (Python file)
# 2 vCPU 容器基线；OCR 在后台线程池执行，不阻塞请求 worker
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
bind = "0.0.0.0:5001"

# OCR 同步路径（非 XHR 回退）最长可能 60s，留足余量
timeout = 120
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = "info"
