#!/bin/bash
echo "--- PUERTOS ESCUCHANDO ---"
sudo netstat -tlpn | grep -E ":80 |:8000 "
echo "--- DOCKER CONTAINERS ---"
sudo docker ps
echo "--- SERVICIO NGINX ---"
sudo systemctl status nginx --no-pager | head -n 10
echo "--- PRUEBA LOCAL ---"
curl -I http://localhost:8000/ 2>/dev/null | head -n 1
curl -I http://localhost/ 2>/dev/null | head -n 1
