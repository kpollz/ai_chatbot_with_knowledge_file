FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Flat layout: the modules sit in the working directory and import each other by
# bare name, so both entrypoints resolve the same agent with no path setup.
COPY app/ .

# 8123 = the AG-UI agent (main.py); 8501 = the Streamlit app. One image, two
# entrypoints — docker-compose picks one per service.
EXPOSE 8123 8501

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8123"]
