FROM python:3.12-slim

WORKDIR /app

# Ставимо залежності окремим шаром, щоб кешувалось при змінах коду
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Дані (БД, логи) зберігаються тут — монтуємо як том у docker-compose.yml
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data

CMD ["python", "bot.py"]
