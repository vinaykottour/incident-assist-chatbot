FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
EXPOSE 5000
RUN useradd --create-home appuser
USER appuser
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]