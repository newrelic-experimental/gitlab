FROM dpacheconr/gitlab-exporter-base:1.0.1

WORKDIR /app

COPY get_resources.py .
COPY global_variables.py .
COPY main.py .

ENTRYPOINT [ "python3", "-u" , "main.py"]