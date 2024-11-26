# Use the official Python image from the Docker Hub
FROM python:3.10

# Set the working directory in the container
WORKDIR /app

# Install Poetry
RUN pip install --upgrade pip
RUN pip install poetry

# Copy only the pyproject.toml and poetry.lock files
COPY pyproject.toml poetry.lock ./

# Install the dependencies
RUN poetry install --no-root

# Copy application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]