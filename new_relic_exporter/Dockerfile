FROM python:3.12-slim-bookworm

WORKDIR /app

COPY . .

RUN pip3 install -r shared/requirements.txt

ENV PYTHONPATH=/app

ENTRYPOINT [ "python3", "-u" , "new_relic_exporter/main.py"]