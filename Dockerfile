FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway сам устанавливает PORT переменную
CMD ["python", "bot.py"]
