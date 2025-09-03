FROM python:3.12-slim-bookworm

WORKDIR /app

COPY . .

# Copy main.py to /app/main.py for compatibility with documentation and entrypoint
RUN cp new_relic_exporter/main.py /app/main.py

RUN pip3 install -r shared/requirements.txt

ENV PYTHONPATH=/app

ENTRYPOINT [ "python3", "-u" , "/app/main.py"]
