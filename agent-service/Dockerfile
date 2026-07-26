FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# The agent primitives (tools, prompt, LLM factory, Langfuse setup) are reused
# from the chatbot sub-project, mounted here by docker-compose. Its modules use
# flat imports, so the directory itself goes on the path.
ENV PYTHONPATH=/chatbot_app

EXPOSE 8700

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8700"]
