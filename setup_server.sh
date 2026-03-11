#!/bin/bash
cat << 'EOF' > /etc/systemd/system/zerf_api.service
[Unit]
Description=Zerf Transcriptor FastAPI Server
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/servidor/transcripciones/zerf_transcriptor
ExecStart=/usr/bin/env python3 manager_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable zerf_api
systemctl restart zerf_api
systemctl status zerf_api --no-pager
