# Imagem base lightweight
FROM python:3.11-slim

# Evita gerar arquivos .pyc e garante logs imediatos
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala as dependências de sistema para o GeoDjango e SpatiaLite
# O 'rm -rf /var/lib/apt/lists/*' ajuda a manter a imagem leve apagando o cache do apt
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    libsqlite3-mod-spatialite \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia e instala as dependências primeiro (aproveitando o cache do Docker)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia todo o código do projeto para o diretório de trabalho do container (/app)
COPY . .

# Cria diretório para arquivos de mídia (caso necessário)
RUN mkdir -p /app/media

# Expõe a porta padrão do Django/uvicorn
EXPOSE 8000

# Comando padrão (pode ser sobrescrito no docker-compose.yml)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]