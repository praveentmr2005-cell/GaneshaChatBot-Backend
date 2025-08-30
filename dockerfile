# 1. Start with a standard, lightweight Python image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Install only the essential system dependency: ffmpeg
# This is still needed to convert the user's uploaded audio.
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# 4. Copy and install Python requirements
# This is done first to take advantage of Docker's layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your application code
COPY app.py .
COPY main ./main

# 6. Expose the port your application will run on
EXPOSE 8000

# 7. The command to run your Flask app in production
CMD ["gunicorn", "--workers", "2", "--threads", "2", "--bind", "0.0.0.0:8000", "app:app"]
