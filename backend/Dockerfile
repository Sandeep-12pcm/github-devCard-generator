FROM python:3.12-slim

# Install uv from the official pre-built image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies using uv to ensure extremely fast builds
RUN uv pip install --system --no-cache -r requirements.txt

# Copy backend application source code
COPY . .

# Expose backend port
EXPOSE 8080

# Command to execute the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
