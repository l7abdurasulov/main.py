# Python'ning engil versiyasini tanlaymiz
FROM python:3.10-slim

# Tizimga ffmpeg'ni o'rnatamiz (yt-dlp musiqa va videolarni qayta ishlashi uchun juda muhim)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Konteyner ichidagi ishchi papkani yaratamiz
WORKDIR /app

# Avval requirements.txt faylini ko'chirib, kutubxonalarni o'rnatamiz (keshdan unumli foydalanish uchun)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Qolgan barcha fayllarni (main.py va boshqalar) konteynerga ko'chiramiz
COPY . .

# Flask serveri ishlaydigan portni ochamiz (Render/Railway talabiga mos)
EXPOSE 8080

# Botni ishga tushirish buyrug'i
CMD ["python", "main.py"]
