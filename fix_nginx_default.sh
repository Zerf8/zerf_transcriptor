#!/bin/bash
echo "Eliminando sitio default de Nginx..."
sudo rm -f /etc/nginx/sites-enabled/default

echo "Verificando enlace simbólico..."
sudo ln -sf /etc/nginx/sites-available/zerf_web /etc/nginx/sites-enabled/zerf_web

echo "Verificando configuración de Nginx..."
sudo nginx -t

echo "Reiniciando Nginx..."
sudo systemctl restart nginx
echo "Hecho."
