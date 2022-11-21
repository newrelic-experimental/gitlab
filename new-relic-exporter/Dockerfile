FROM ghcr.io/newrelic-experimental/gitlab/new-relic-exporter-base:1.0.0

WORKDIR /app

COPY exporter.py .

ENTRYPOINT [ "python3", "-u" , "exporter.py"]