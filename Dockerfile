FROM python:3.13-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  gcc \
  curl

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENV PORT=7070

EXPOSE $PORT

CMD ["make", "run"]
