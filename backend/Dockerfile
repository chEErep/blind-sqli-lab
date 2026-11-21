FROM python:3.12-slim

WORKDIR /app

# Сначала зависимости (для кэширования слоёв)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Затем код приложения
COPY . .

EXPOSE 8080
CMD ["python", "app.py"]
