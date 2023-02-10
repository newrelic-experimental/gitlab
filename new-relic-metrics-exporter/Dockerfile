FROM dpacheconr/gitlab-exporter-base:1.0.1

WORKDIR /app

COPY metrics-exporter.py .

ENTRYPOINT [ "python3", "-u" , "metrics-exporter.py"]