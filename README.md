# 🌡️ Monitor Temperatura DS18B20 — Raspberry Pi + GitHub Pages

Sistema complet de monitoratge de temperatura amb sensor DS18B20, emmagatzemament local CSV, dashboard web (GitHub Pages) i API REST per a app mòbil.

---

## 📁 Estructura del Projecte

```
temperature-monitor/
├── raspberry/
│   ├── sensor_reader.py      # ⭐ Script principal
│   ├── export_stats.py       # Exportació d'estadístiques
│   ├── config.json           # Configuració (edita aquest!)
│   ├── requirements.txt      # Dependències Python
│   ├── setup_raspberry.sh    # Instal·lació automàtica
│   └── data/                 # CSVs locals (creat automàticament)
│       ├── temperature_YYYY-MM.csv
│       └── sensor.log
├── web/
│   ├── index.html            # Dashboard GitHub Pages
│   └── data.json             # Dades en temps real (actualitzat automàticament)
├── .vscode/
│   ├── settings.json
│   └── launch.json           # Configuració de debug VS Code
└── README.md
```

---

## ⚡ Instal·lació Ràpida (Raspberry Pi)

### 1. Clonar/copiar el projecte a la Raspberry
```bash
git clone https://github.com/EL_TEU_USUARI/EL_TEU_REPO.git
cd EL_TEU_REPO
```

### 2. Executar script d'instal·lació
```bash
cd raspberry
bash setup_raspberry.sh
```

### 3. Cablejat del sensor DS18B20
```
DS18B20          Raspberry Pi
─────────────────────────────
Vermell (VCC)  → Pin 1  (3.3V)
Negre   (GND)  → Pin 6  (GND)
Groc    (DATA) → Pin 7  (GPIO4)

⚠️ IMPORTANT: Afegir resistència pull-up de 4.7kΩ
   entre DATA i VCC
```

### 4. Activar 1-Wire (si no ho ha fet setup_raspberry.sh)
```bash
# Afegir a /boot/config.txt:
dtoverlay=w1-gpio

# O amb raspi-config:
sudo raspi-config → Interface Options → 1-Wire → Enable

# Reiniciar:
sudo reboot
```

### 5. Configurar config.json
Edita `raspberry/config.json`:
```json
{
  "github": {
    "token": "",   ← Token GitHub (Settings > Developer settings > Personal access tokens)
    "username": "Sergitronix-jpg",
    "repo": "monitor-temperatura1",
    "branch": "main"
  }
}
```

---

## 🚀 Execució

### Mode normal (sensor físic)
```bash
python3 raspberry/sensor_reader.py
```

### Mode simulació (proves sense sensor)
```bash
python3 raspberry/sensor_reader.py --simulate
```

### Canviar interval
```bash
python3 raspberry/sensor_reader.py --interval 60   # cada 60 segons
```

### Des de VS Code
Obre el projecte i prem **F5** (Run and Debug), selecciona la configuració desitjada.

---

## 🌐 GitHub Pages

### Configuració inicial
1. Ves a Settings → Pages del teu repositori GitHub
2. Selecciona "Deploy from branch" → `main` → `/web`
3. La web serà accessible a: `https://EL_TEU_USUARI.github.io/EL_TEU_REPO`

El sensor actualitza `web/data.json` automàticament a cada lectura.

---

## 📱 API REST (App Mòbil)

L'API s'inicia automàticament al port **5000** (configurable).

### Endpoints
| Mètode | URL | Descripció |
|--------|-----|------------|
| GET | `/api/health` | Estat del servidor |
| GET | `/api/current` | Temperatura actual |
| GET | `/api/readings?hours=24&limit=100` | Últimes lectures |
| GET | `/api/stats` | Estadístiques 24h/7d/30d |
| POST | `/api/reading` | Afegir lectura externa |

### Autenticació
Totes les peticions (excepte `/api/health` i `/api/current`) requereixen:
```
Header: X-API-Token: <sha256(secret_key)>
```

Calcula el token:
```python
import hashlib
secret = "temperatura1234"  # valor de config.json
token = hashlib.sha256(secret.encode()).hexdigest()
```

### Exemple (curl)
```bash
# Temperatura actual (sense autenticació)
curl http://raspberry.local:5000/api/current

# Estadístiques (amb token)
curl -H "X-API-Token: <token>" http://raspberry.local:5000/api/stats

# Afegir lectura externa
curl -X POST -H "Content-Type: application/json" \
     -H "X-API-Token: <token>" \
     -d '{"temperature_c": 23.5, "sensor_id": "MOBIL-01"}' \
     http://raspberry.local:5000/api/reading
```

---

## 📊 Exportació d'Estadístiques

```bash
# JSON (últims 30 dies)
python3 raspberry/export_stats.py --format json --days 30

# CSV
python3 raspberry/export_stats.py --format csv --days 7

# HTML (informe navegador)
python3 raspberry/export_stats.py --format html --days 30 --output informe.html
```

---

## ⚙️ Servei Systemd (Auto-inici)

```bash
# Iniciar
sudo systemctl start temp-monitor

# Aturar
sudo systemctl stop temp-monitor

# Veure logs en temps real
journalctl -u temp-monitor -f

# Deshabilitar auto-inici
sudo systemctl disable temp-monitor
```

---

## 📧 Alertes per Email (Opcional)

Edita `config.json`:
```json
"notifications": {
  "email_enabled": true,
  "email_user": "sergio261106@gmail.com",
  "email_password": "gbmu lznc ezig ozou",
  "email_to": "sergio261106@gmail.com",
  "alert_on_threshold": true
}
```

Per Gmail, cal crear una **contrasenya d'aplicació**:
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

---

## 🔧 Resolució de Problemes

### Sensor no trobat
```bash
# Comprova dispositius 1-Wire
ls /sys/bus/w1/devices/
# Ha d'aparèixer un directori "28-xxxxxxxxxxxx"

# Comprova el kernel
lsmod | grep w1
```

### GitHub no s'actualitza
- Comprova que el token tingui permisos `repo` o `contents:write`
- Verifica `username`, `repo` i `branch` a `config.json`
- Revisa els logs: `data/sensor.log`

### API no accessible des d'un altre dispositiu
```bash
# Comprova el firewall
sudo ufw allow 5000/tcp

# Comprova la IP de la Raspberry
hostname -I
```

---

## 🆕 Funcionalitats Addicionals Implementades

- ✅ Rotació mensual automàtica de CSVs
- ✅ Alertes per email en temperatura extrema (amb cooldown anti-spam)
- ✅ API REST per app mòbil (GET/POST)
- ✅ Mode simulació per a proves sense sensor
- ✅ Servei systemd per a auto-inici
- ✅ Dashboard web responsiu amb gràfics interactius
- ✅ Estadístiques per franja horària i per dia
- ✅ Exportació JSON/CSV/HTML
- ✅ Configuració per arguments de línia de comandes
- ✅ Push asíncron a GitHub (no bloqueja el cicle de lectura)
- ✅ Configuració VS Code (launch.json, settings.json)
