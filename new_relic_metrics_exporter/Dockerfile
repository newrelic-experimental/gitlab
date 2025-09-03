
FROM python:3.13.7-alpine3.22

WORKDIR /app

# Install system dependencies needed for building Python packages
RUN apk add --no-cache \
    gcc \
    g++ \
    musl-dev \
    linux-headers

COPY . .

RUN cp new_relic_metrics_exporter/main.py /app/main.py && \
    cp new_relic_metrics_exporter/get_resources.py /app/get_resources.py

# Upgrade pip and install packages
RUN pip3 install --upgrade pip && \
    pip3 install -r shared/requirements.txt

ENV PYTHONPATH=/app

ENTRYPOINT [ "python3", "-u" , "/app/main.py"]
