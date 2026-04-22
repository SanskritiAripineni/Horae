FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py agent.py config.py db.py ./
COPY tools/ tools/
COPY memory/ memory/
COPY vectordb/ vectordb/
COPY wellbeing_pipeline/ wellbeing_pipeline/
COPY startup.sh startup.sh
RUN chmod +x startup.sh

EXPOSE 8000
CMD ["/bin/sh", "startup.sh"]
