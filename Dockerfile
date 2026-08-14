FROM python:3.12-slim

WORKDIR /app

# 安装 Python 依赖
# psycopg2-binary 是预编译版本，无需 build-essential / libpq-dev
COPY server/requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.mirrors.ustc.edu.cn/simple -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]