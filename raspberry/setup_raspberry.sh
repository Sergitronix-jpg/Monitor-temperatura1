#!/bin/bash
# =============================================================
#  SCRIPT D'INSTAL·LACIÓ - Monitor Temperatura DS18B20
#  Executa com: bash setup_raspberry.sh
# =============================================================

set -e

echo "================================================"
echo "  🌡️  Instal·lació Monitor Temperatura DS18B20"
echo "================================================"

# 1. Activar interfície 1-Wire
echo ""
echo "📡 Configurant 1-Wire..."
if ! grep -q "dtoverlay=w1-gpio" /boot/config.txt 2>/dev/null; then
    echo "dtoverlay=w1-gpio" | sudo tee -a /boot/config.txt
    echo "✅ 1-Wire afegit a /boot/config.txt"
else
    echo "✅ 1-Wire ja configurat"
fi

# Carregar mòduls kernel
sudo modprobe w1-gpio 2>/dev/null || true
sudo modprobe w1-therm 2>/dev/null || true

# 2. Actualitzar pip i instal·lar dependències
echo ""
echo "📦 Instal·lant dependències Python..."
pip3 install --upgrade pip --quiet
pip3 install -r requirements.txt --quiet
echo "✅ Dependències instal·lades"

# 3. Crear directoris de dades
mkdir -p data
echo "✅ Directori data/ creat"

# 4. Configurar servei systemd (execució automàtica en iniciar)
echo ""
echo "⚙️  Configurant servei systemd..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="/etc/systemd/system/temp-monitor.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Monitor Temperatura DS18B20
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/sensor_reader.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable temp-monitor.service
echo "✅ Servei creat: temp-monitor.service"

echo ""
echo "================================================"
echo "  ✅ Instal·lació completada!"
echo "================================================"
echo ""
echo "  📝 Passos següents:"
echo "  1. Edita config.json i configura el teu GitHub token"
echo "  2. Connecta el sensor DS18B20:"
echo "     - Vermell (VCC) → Pin 1 (3.3V)"
echo "     - Negre  (GND) → Pin 6 (GND)"
echo "     - Groc   (DATA)→ Pin 7 (GPIO4) + resistència 4.7kΩ a VCC"
echo ""
echo "  🚀 Iniciar ara:"
echo "     sudo systemctl start temp-monitor"
echo "     sudo systemctl status temp-monitor"
echo ""
echo "  🔍 Veure logs:"
echo "     journalctl -u temp-monitor -f"
echo ""
echo "  🎭 Proves sense sensor:"
echo "     python3 sensor_reader.py --simulate --interval 5"
echo ""
