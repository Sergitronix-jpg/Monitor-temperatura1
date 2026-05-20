#!/usr/bin/env python3
"""
=============================================================
  MONITOR DE TEMPERATURA DS18B20 - Raspberry Pi
  Sensor: Binghe DS18B20 (IP68, -55°C a +125°C)
=============================================================
  Ús:
    python3 sensor_reader.py              # Mode normal
    python3 sensor_reader.py --simulate   # Mode simulació (sense sensor físic)
    python3 sensor_reader.py --interval 60  # Canviar interval
=============================================================
"""

import os
import sys
import csv
import json
import time
import random
import logging
import argparse
import threading
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Afegim el path del projecte
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# CONFIGURACIÓ DE LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "sensor.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# CÀRREGA DE CONFIGURACIÓ
# ─────────────────────────────────────────────
def load_config() -> dict:
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        log.error(f"No s'ha trobat config.json a {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# LECTURA DEL SENSOR DS18B20 (1-Wire)
# ─────────────────────────────────────────────
DS18B20_BASE_PATH = Path("/sys/bus/w1/devices")

def find_sensor() -> Path | None:
    """Cerca el dispositiu DS18B20 al sistema 1-Wire."""
    if not DS18B20_BASE_PATH.exists():
        return None
    for device in DS18B20_BASE_PATH.iterdir():
        if device.name.startswith("28-"):
            return device / "w1_slave"
    return None


def read_ds18b20(sensor_path: Path) -> float | None:
    """Llegeix la temperatura del sensor DS18B20."""
    try:
        raw = sensor_path.read_text()
        lines = raw.strip().splitlines()
        if len(lines) < 2 or "YES" not in lines[0]:
            log.warning("Lectura del sensor invàlida (no YES)")
            return None
        temp_str = lines[1].split("t=")[-1]
        return round(float(temp_str) / 1000.0, 2)
    except Exception as e:
        log.error(f"Error llegint sensor: {e}")
        return None


def simulate_temperature(cfg: dict) -> float:
    """Genera una temperatura simulada per a proves sense sensor físic."""
    base = (cfg["sensor"]["simulate_min_temp"] + cfg["sensor"]["simulate_max_temp"]) / 2
    variation = random.uniform(-2.0, 2.0)
    hour = datetime.now().hour
    # Simula variació diürna (més calent al migdia)
    daily_curve = 3.0 * ((hour - 6) / 12.0) if 6 <= hour <= 18 else -1.5
    return round(base + variation + daily_curve, 2)


# ─────────────────────────────────────────────
# EMMAGATZEMAMENT LOCAL (CSV)
# ─────────────────────────────────────────────
def get_csv_path(cfg: dict) -> Path:
    """Retorna el path del CSV (amb rotació mensual si s'ha configurat)."""
    if cfg["storage"]["rotate_csv_monthly"]:
        month_str = datetime.now().strftime("%Y-%m")
        return DATA_DIR / f"temperature_{month_str}.csv"
    return DATA_DIR / cfg["storage"]["csv_path"].split("/")[-1]


CSV_HEADER = ["timestamp", "iso_date", "temperature_c", "sensor_id", "valid"]


def save_to_csv(temp: float, cfg: dict, sensor_id: str = "DS18B20-01"):
    """Desa una lectura al fitxer CSV local."""
    csv_path = get_csv_path(cfg)
    now = datetime.now()
    row = {
        "timestamp": int(now.timestamp()),
        "iso_date": now.isoformat(),
        "temperature_c": temp,
        "sensor_id": sensor_id,
        "valid": 1,
    }

    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    # Comprova límit de files
    max_rows = cfg["storage"]["max_csv_rows"]
    if file_exists:
        with open(csv_path, "r", encoding="utf-8") as f:
            total = sum(1 for _ in f)
        if total > max_rows + 1:
            log.warning(f"CSV supera {max_rows} registres. Considera arxivar.")


def load_recent_readings(hours: int = 24) -> list[dict]:
    """Carrega les lectures de les últimes N hores des del CSV."""
    results = []
    cutoff = datetime.now() - timedelta(hours=hours)
    for csv_file in sorted(DATA_DIR.glob("temperature_*.csv"), reverse=True):
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        dt = datetime.fromisoformat(row["iso_date"])
                        if dt >= cutoff:
                            results.append({
                                "timestamp": int(row["timestamp"]),
                                "iso_date": row["iso_date"],
                                "temperature_c": float(row["temperature_c"]),
                            })
                    except (ValueError, KeyError):
                        continue
        except Exception as e:
            log.error(f"Error llegint {csv_file}: {e}")
    return sorted(results, key=lambda x: x["timestamp"])


def compute_statistics(readings: list[dict]) -> dict:
    """Calcula estadístiques a partir d'una llista de lectures."""
    if not readings:
        return {}
    temps = [r["temperature_c"] for r in readings]
    return {
        "count": len(temps),
        "min": round(min(temps), 2),
        "max": round(max(temps), 2),
        "avg": round(sum(temps) / len(temps), 2),
        "last": temps[-1],
        "last_timestamp": readings[-1]["iso_date"],
    }


# ─────────────────────────────────────────────
# ACTUALITZACIÓ GITHUB PAGES (JSON)
# ─────────────────────────────────────────────
def build_github_json(cfg: dict) -> dict:
    """Construeix el JSON complet per a GitHub Pages."""
    now = datetime.now()

    readings_24h = load_recent_readings(hours=24)
    readings_7d = load_recent_readings(hours=168)
    readings_30d = load_recent_readings(hours=720)

    # Estadístiques per franja horària (últim mes)
    hourly_stats = {}
    for r in readings_30d:
        hour = datetime.fromisoformat(r["iso_date"]).hour
        key = f"{hour:02d}:00"
        hourly_stats.setdefault(key, []).append(r["temperature_c"])

    hourly_avg = {
        h: round(sum(v) / len(v), 2)
        for h, v in sorted(hourly_stats.items())
    }

    # Estadístiques per dia (últims 30 dies)
    daily_stats = {}
    for r in readings_30d:
        day = r["iso_date"][:10]
        daily_stats.setdefault(day, []).append(r["temperature_c"])

    daily_summary = {
        day: {
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
            "avg": round(sum(vals) / len(vals), 2),
            "count": len(vals),
        }
        for day, vals in sorted(daily_stats.items())
    }

    return {
        "generated_at": now.isoformat(),
        "sensor": "DS18B20",
        "location": "Raspberry Pi",
        "current": readings_24h[-1] if readings_24h else None,
        "stats": {
            "last_24h": compute_statistics(readings_24h),
            "last_7d": compute_statistics(readings_7d),
            "last_30d": compute_statistics(readings_30d),
        },
        "readings_24h": readings_24h[-288:],  # màxim 288 punts (30s interval)
        "hourly_avg_30d": hourly_avg,
        "daily_summary": daily_summary,
    }


def push_to_github(cfg: dict, json_data: dict) -> bool:
    """Actualitza el fitxer data.json al repositori de GitHub via API."""
    try:
        import urllib.request
        import base64

        gh = cfg["github"]
        if not gh.get("enabled") or gh["token"] == "GITHUB_TOKEN_AQUI":
            log.warning("GitHub no configurat o desactivat.")
            return False

        content = json.dumps(json_data, ensure_ascii=False, indent=2)
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        api_url = (
            f"https://api.github.com/repos/{gh['username']}/{gh['repo']}"
            f"/contents/{gh['data_file_path']}"
        )
        headers = {
            "Authorization": f"token {gh['token']}",
            "Content-Type": "application/json",
            "User-Agent": "RaspberryTempMonitor/1.0",
        }

        # Obté el SHA actual (necessari per actualitzar)
        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                existing = json.loads(resp.read())
                sha = existing.get("sha", "")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                sha = ""  # El fitxer no existeix, el crearem
            else:
                raise

        payload = {
            "message": f"📊 Actualització temperatura {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": encoded,
            "branch": gh["branch"],
        }
        if sha:
            payload["sha"] = sha

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(api_url, data=data, headers=headers, method="PUT")
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                log.info("✅ GitHub Pages actualitzat correctament")
                return True
    except Exception as e:
        log.error(f"❌ Error actualitzant GitHub: {e}")
    return False


# ─────────────────────────────────────────────
# ALERTES PER EMAIL
# ─────────────────────────────────────────────
_last_alert_sent: dict[str, datetime] = {}


def send_alert_email(cfg: dict, temp: float, alert_type: str):
    """Envia un email d'alerta si la temperatura supera els límits."""
    notif = cfg.get("notifications", {})
    if not notif.get("email_enabled"):
        return

    # Evitar spam: màxim 1 alerta cada 30 minuts per tipus
    cooldown = timedelta(minutes=30)
    if alert_type in _last_alert_sent:
        if datetime.now() - _last_alert_sent[alert_type] < cooldown:
            return

    try:
        msg = MIMEMultipart()
        msg["From"] = notif["email_user"]
        msg["To"] = notif["email_to"]
        msg["Subject"] = f"⚠️ Alerta temperatura: {temp}°C"

        body = (
            f"S'ha detectat una temperatura {'ALTA' if alert_type == 'high' else 'BAIXA'}!\n\n"
            f"Temperatura actual: {temp}°C\n"
            f"Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"Límit {'màxim' if alert_type == 'high' else 'mínim'}: "
            f"{cfg['sensor']['alert_max_temp'] if alert_type == 'high' else cfg['sensor']['alert_min_temp']}°C"
        )
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(notif["email_smtp"], notif["email_port"]) as server:
            server.starttls()
            server.login(notif["email_user"], notif["email_password"])
            server.send_message(msg)

        _last_alert_sent[alert_type] = datetime.now()
        log.info(f"📧 Email d'alerta enviat: {alert_type}")
    except Exception as e:
        log.error(f"Error enviant email: {e}")


def check_alerts(temp: float, cfg: dict):
    """Comprova si la temperatura supera els límits i envia alertes."""
    notif = cfg.get("notifications", {})
    if not notif.get("alert_on_threshold"):
        return
    if temp >= cfg["sensor"]["alert_max_temp"]:
        log.warning(f"🔥 ALERTA: Temperatura alta! {temp}°C")
        threading.Thread(target=send_alert_email, args=(cfg, temp, "high"), daemon=True).start()
    elif temp <= cfg["sensor"]["alert_min_temp"]:
        log.warning(f"🥶 ALERTA: Temperatura baixa! {temp}°C")
        threading.Thread(target=send_alert_email, args=(cfg, temp, "low"), daemon=True).start()


# ─────────────────────────────────────────────
# API REST LOCAL (per app mòbil)
# ─────────────────────────────────────────────
def start_api_server(cfg: dict):
    """Inicia un servidor Flask lleuger per a l'app mòbil."""
    try:
        from flask import Flask, jsonify, request, abort
        import hashlib

        app = Flask(__name__)
        api_cfg = cfg.get("api", {})
        secret = api_cfg.get("secret_key", "")

        def verify_token():
            token = request.headers.get("X-API-Token", "")
            if not token or token != hashlib.sha256(secret.encode()).hexdigest():
                abort(401, "Token invàlid")

        @app.route("/api/current", methods=["GET"])
        def get_current():
            readings = load_recent_readings(hours=1)
            if not readings:
                return jsonify({"error": "Sense dades"}), 404
            return jsonify(readings[-1])

        @app.route("/api/readings", methods=["GET"])
        def get_readings():
            verify_token()
            hours = int(request.args.get("hours", 24))
            limit = int(request.args.get("limit", 100))
            readings = load_recent_readings(hours=min(hours, 720))
            return jsonify({"readings": readings[-limit:], "total": len(readings)})

        @app.route("/api/stats", methods=["GET"])
        def get_stats():
            verify_token()
            return jsonify({
                "24h": compute_statistics(load_recent_readings(24)),
                "7d": compute_statistics(load_recent_readings(168)),
                "30d": compute_statistics(load_recent_readings(720)),
            })

        @app.route("/api/reading", methods=["POST"])
        def post_reading():
            """Permet afegir lectures externes (app mòbil, altres sensors)."""
            verify_token()
            data = request.get_json(force=True)
            temp = data.get("temperature_c")
            if temp is None:
                return jsonify({"error": "Falta temperature_c"}), 400
            save_to_csv(float(temp), cfg, sensor_id=data.get("sensor_id", "EXTERN"))
            return jsonify({"status": "ok", "temperature_c": temp}), 201

        @app.route("/api/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok", "time": datetime.now().isoformat()})

        host = api_cfg.get("host", "0.0.0.0")
        port = api_cfg.get("port", 5000)
        log.info(f"🌐 API REST iniciada a http://{host}:{port}")
        app.run(host=host, port=port, debug=False, use_reloader=False)

    except ImportError:
        log.warning("Flask no instal·lat. API REST desactivada. Executa: pip install flask")
    except Exception as e:
        log.error(f"Error iniciant API: {e}")


# ─────────────────────────────────────────────
# BUCLE PRINCIPAL
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Monitor de temperatura DS18B20")
    parser.add_argument("--simulate", action="store_true", help="Mode simulació")
    parser.add_argument("--interval", type=int, help="Interval en segons (sobreescriu config.json)")
    parser.add_argument("--no-github", action="store_true", help="No actualitza GitHub")
    parser.add_argument("--no-api", action="store_true", help="No inicia l'API REST")
    args = parser.parse_args()

    cfg = load_config()

    # Sobreescriure configuració per arguments
    if args.simulate:
        cfg["sensor"]["simulate"] = True
    if args.interval:
        cfg["sensor"]["interval_seconds"] = args.interval
    if args.no_github:
        cfg["github"]["enabled"] = False

    interval = cfg["sensor"]["interval_seconds"]
    simulate = cfg["sensor"]["simulate"]
    sensor_path = None

    log.info("=" * 55)
    log.info("  🌡️  MONITOR TEMPERATURA DS18B20 - Raspberry Pi")
    log.info("=" * 55)
    log.info(f"  Mode: {'SIMULACIÓ 🎭' if simulate else 'SENSOR REAL 📡'}")
    log.info(f"  Interval: {interval}s")
    log.info(f"  GitHub: {'✅' if cfg['github']['enabled'] else '❌'}")
    log.info("=" * 55)

    # Inicia l'API en un fil separat
    if not args.no_api and cfg.get("api", {}).get("enabled"):
        api_thread = threading.Thread(target=start_api_server, args=(cfg,), daemon=True)
        api_thread.start()

    if not simulate:
        sensor_path = find_sensor()
        if sensor_path:
            log.info(f"✅ Sensor trobat: {sensor_path}")
        else:
            log.error("❌ Sensor DS18B20 no trobat! Comprova el cablejat i que 1-Wire estigui activat.")
            log.error("   Executa: sudo raspi-config → Interface Options → 1-Wire → Enable")
            log.error("   Afegeix a /boot/config.txt: dtoverlay=w1-gpio")
            log.error("   Reinicia i torna a executar, o usa --simulate per proves.")
            sys.exit(1)

    reading_count = 0
    push_every = cfg["github"].get("push_every_n_readings", 1)

    try:
        while True:
            start_time = time.time()

            # Llegir temperatura
            if simulate:
                temp = simulate_temperature(cfg)
                log.info(f"🎭 [SIMULACIÓ] Temperatura: {temp}°C")
            else:
                temp = read_ds18b20(sensor_path)
                if temp is None:
                    log.warning("Lectura fallida, reintentant al proper cicle...")
                    time.sleep(interval)
                    continue
                log.info(f"🌡️  Temperatura: {temp}°C")

            # Desar al CSV
            save_to_csv(temp, cfg)

            # Comprovar alertes
            check_alerts(temp, cfg)

            reading_count += 1

            # Actualitzar GitHub (cada N lectures)
            if cfg["github"]["enabled"] and reading_count % push_every == 0:
                github_data = build_github_json(cfg)
                push_thread = threading.Thread(
                    target=push_to_github, args=(cfg, github_data), daemon=True
                )
                push_thread.start()

            # Esperar fins al proper cicle (compensant el temps de processament)
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            log.debug(f"Propera lectura en {sleep_time:.1f}s")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info("\n⏹️  Monitor aturat per l'usuari.")
    except Exception as e:
        log.critical(f"Error crític: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
