FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .[web]
EXPOSE 8000
CMD ["python", "-m", "opendemocracy.web", "--host", "0.0.0.0", "--port", "8000"]
