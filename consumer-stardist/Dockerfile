FROM python:3.12-slim

# Required by NumPy (OpenMP) and some TF I/O operations (GLib)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# consumer-common is referenced as "-e ../consumer-common" in requirements.txt;
# from WORKDIR /app that path resolves to /consumer-common.
COPY consumer-common/ /consumer-common/

COPY consumer-stardist/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer-stardist/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
