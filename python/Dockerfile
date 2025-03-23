FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache sqlite
COPY . /app/
COPY main.py .
COPY db/items.sql /app/db/items.sql
COPY mercari.sqlite3 /app/db/mercari.sqlite3
COPY requirements.txt ./app/
RUN pip install --no-cache-dir -r requirements.txt
CMD sqlite3 /app/db/mercari.sqlite3 < /app/db/items.sql && \
    python -m uvicorn main:app --reload --log-level debug --host 0.0.0.0 --port 9000