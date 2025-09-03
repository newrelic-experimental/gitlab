
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY . .

RUN cp new_relic_metrics_exporter/main.py /app/main.py && \
    cp new_relic_metrics_exporter/get_resources.py /app/get_resources.py

RUN pip3 install -r shared/requirements.txt

ENV PYTHONPATH=/app

ENTRYPOINT [ "python3", "-u" , "/app/main.py"]
