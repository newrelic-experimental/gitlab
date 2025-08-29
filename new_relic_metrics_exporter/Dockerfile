FROM dpacheconr/gitlab-exporter-base

WORKDIR /app

COPY . .

ENV PYTHONPATH=/app

ENTRYPOINT [ "python3", "-u" , "/app/main.py"]