#!/bin/bash
echo "Instalando Nginx..."
sudo apt-get update
sudo apt-get install -y nginx

echo "Configurando Nginx para el puerto 80..."
# Copy the updated nginx.conf to sites-available
sudo cp /home/ubuntu/servidor/transcripciones/zerf_transcriptor/nginx.conf /etc/nginx/sites-available/zerf_web
sudo ln -sf /etc/nginx/sites-available/zerf_web /etc/nginx/sites-enabled/zerf_web

# Remove default site to avoid port 80 conflict
sudo rm -f /etc/nginx/sites-enabled/default

echo "Reiniciando servicios..."
sudo systemctl restart nginx
sudo systemctl enable nginx

echo "¡Completado! El puerto 80 ahora redirige al 8000 de forma nativa."
