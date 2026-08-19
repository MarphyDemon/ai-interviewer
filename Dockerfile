FROM python:3.12-slim

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app

COPY server/requirements.txt .

RUN pip config set global.index-url ${PIP_INDEX_URL} && \
    pip config set global.trusted-host ${PIP_TRUSTED_HOST} && \
    pip config set global.timeout 30 && \
    pip install --no-cache-dir -r requirements.txt

# 复制后端源代码
COPY server/ ./server/
COPY src/ ./src/
COPY .env.web .

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]