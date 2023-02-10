FROM dpacheconr/gitlab-exporter-base:1.0.1

WORKDIR /app

COPY exporter.py .

ENTRYPOINT [ "python3", "-u" , "exporter.py"]