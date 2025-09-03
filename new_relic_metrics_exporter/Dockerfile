
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY . .

# Copy improved_main.py to /app/main.py for better architecture and error handling
RUN cp new_relic_metrics_exporter/main.py /app/main.py

RUN pip3 install -r shared/requirements.txt

ENV PYTHONPATH=/app

ENTRYPOINT [ "python3", "-u" , "/app/main.py"]
