FROM python:alpine

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Generate a .env file with a random SECRET_KEY
RUN python -c "import os; print(f'SECRET_KEY={os.urandom(24).hex()}')" > .env

EXPOSE 5000

# Use gunicorn to serve the Flask app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]