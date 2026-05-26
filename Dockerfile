FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create runtime directories
RUN mkdir -p database logs

# Environment variables (override via docker run -e or .env)
ENV DERIV_API_TOKEN=""
ENV DERIV_APP_ID="1089"

CMD ["python", "main.py"]
