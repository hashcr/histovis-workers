FROM python:3.12-slim

# OpenSlide and tiatoolbox system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libopenjp2-7 \
    libtiff6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY consumer-common/ /consumer-common/

COPY consumer-tileserver/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer-tileserver/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
