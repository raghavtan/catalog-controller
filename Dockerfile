FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY controller.py .

# Run the controller
CMD ["kopf", "run", "controller.py", "--standalone", "--verbose"]