FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install dependencies first — Docker caches this layer
# If requirements.txt hasn't changed, this step is skipped on rebuild
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create a directory for the SQLite database file
# This gets mounted as a volume so data persists between restarts
RUN mkdir -p /app/data

# Expose the port uvicorn will listen on
EXPOSE 8000

# Start the server
# host 0.0.0.0 makes it accessible from outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
