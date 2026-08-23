FROM python:3.12-slim

# llama-cpp-python compiles C++ extensions at install time
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# consumer-common is referenced as "-e ../consumer-common" in requirements.txt;
# from WORKDIR /app that path resolves to /consumer-common.
COPY consumer-common/ /consumer-common/

COPY consumer-qwen/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer-qwen/ .

RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
