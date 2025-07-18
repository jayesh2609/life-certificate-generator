# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# **FIX IS HERE**: Install Tesseract AND the missing graphics library for OpenCV
RUN apt-get update && apt-get install -y tesseract-ocr libgl1-mesa-glx && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Make port 10000 available to the world outside this container
EXPOSE 10000

# **FIX IS HERE**: Switch back to the production-ready Gunicorn server
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]