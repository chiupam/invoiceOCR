FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# 创建必要的目录
RUN mkdir -p data/output app/static/uploads

# 设置环境变量
ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 5001

# 启动应用
CMD ["python3", "run.py"] 