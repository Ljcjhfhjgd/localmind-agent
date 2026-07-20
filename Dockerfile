FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://ollama.com/install.sh | sh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ ./agent/
COPY llm/ ./llm/
COPY server/ ./server/
COPY tools/ ./tools/
COPY config.yaml .
COPY start.py .

RUN mkdir -p data/conversations data/uploads data/rag_db logs

EXPOSE 8765

COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]