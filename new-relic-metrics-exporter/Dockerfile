FROM dpacheconr/gitlab-exporter-base:1.0.0

WORKDIR /app

COPY metrics-exporter.py .

ENTRYPOINT [ "python3", "-u" , "metrics-exporter.py"]