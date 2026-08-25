FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn
COPY . .
# LLM_API_KEY and API_KEY are injected as environment variables at deploy
EXPOSE 8080
CMD ["uvicorn", "copilot-studio.api:app", "--host", "0.0.0.0", "--port", "8080"]
