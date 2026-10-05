# Usar imagen base ligera de Python 3.12
FROM python:3.12-slim

# Metadatos
LABEL maintainer="Anime Quiz Team"
LABEL description="API Backend para Anime Quiz con FastAPI"

# Evitar que Python escriba archivos .pyc y forzar salida sin buffer para ver logs inmediatamente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instalar dependencias del sistema mínimas necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements primero para aprovechar la caché de capas de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Crear el directorio para almacenamiento de imágenes si no existe
RUN mkdir -p /app/img

# Exponer el puerto en el que corre FastAPI / Uvicorn
EXPOSE 8000

# Verificación de salud del contenedor
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Comando para ejecutar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
