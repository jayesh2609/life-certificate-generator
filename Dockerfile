# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies, including Tesseract OCR
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Make port 10000 available to the world outside this container
# Render will automatically map this to its public-facing ports
EXPOSE 10000

# Define the command to run your app using Gunicorn
# This tells Gunicorn to listen on all network interfaces on the port Render provides
CMD ["python", "app.py"]