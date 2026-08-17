FROM python:3.12-slim

WORKDIR /app

# 配置 DNS 并安装依赖
COPY server/requirements.txt .

# 使用多种镜像源重试，每次失败都尝试下一个
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com && \
    pip config set global.timeout 30 && \
    pip install --no-cache-dir -r requirements.txt || \
    pip install --no-cache-dir \
      -i https://pypi.tuna.tsinghua.edu.cn/simple \
      --trusted-host pypi.tuna.tsinghua.edu.cn \
      -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt

# 复制后端源代码
COPY server/ ./server/
COPY src/ ./src/
COPY .env.web .

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]