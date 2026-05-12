# Imagem base lightweight
FROM python:3.11-slim

# Evita gerar arquivos .pyc e garante logs imediatos
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia e instala as dependências primeiro (cache do Docker)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia todo o código do projeto para o container
COPY . .

# Cria diretório para arquivos de mídia (caso necessário)
RUN mkdir -p /app/media

# Expõe a porta padrão do Django/uvicorn
EXPOSE 8000

# Comando padrão (pode ser sobrescrito no compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]