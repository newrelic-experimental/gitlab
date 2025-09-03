FROM python:3.13.7-slim

WORKDIR /app

COPY . .

RUN cp new_relic_exporter/main.py /app/main.py

RUN pip3 install -r shared/requirements.txt

ENV PYTHONPATH=/app

ENTRYPOINT [ "python3", "-u" , "/app/main.py"]
