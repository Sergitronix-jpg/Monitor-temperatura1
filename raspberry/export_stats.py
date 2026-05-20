#!/usr/bin/env python3
"""
Exporta estadístiques en format JSON, CSV o HTML
Ús: python3 export_stats.py [--format json|csv|html] [--days 30]
"""
import json
import csv
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
from sensor_reader import load_recent_readings, compute_statistics, load_config, DATA_DIR


def export_json(readings, stats, output_path):
    data = {
        "exported_at": datetime.now().isoformat(),
        "stats": stats,
        "readings": readings,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON exportat: {output_path}")


def export_csv(readings, output_path):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "iso_date", "temperature_c"])
        writer.writeheader()
        writer.writerows(readings)
    print(f"✅ CSV exportat: {output_path}")


def export_html(readings, stats, days, output_path):
    rows = "\n".join(
        f'<tr><td>{r["iso_date"]}</td><td class="temp">{r["temperature_c"]}°C</td></tr>'
        for r in reversed(readings[-100:])
    )
    html = f"""<!DOCTYPE html>
<html lang="ca">
<head>
  <meta charset="UTF-8">
  <title>Informe Temperatura - {datetime.now().strftime('%d/%m/%Y')}</title>
  <style>
    body {{ font-family: monospace; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
    h1 {{ color: #38bdf8; }}
    .stats {{ display: flex; gap: 2rem; margin: 1.5rem 0; flex-wrap: wrap; }}
    .stat {{ background: #1e293b; padding: 1rem 1.5rem; border-radius: 8px; }}
    .stat-value {{ font-size: 2rem; color: #38bdf8; font-weight: bold; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 600px; }}
    th {{ background: #1e293b; padding: .5rem 1rem; text-align: left; color: #94a3b8; }}
    td {{ padding: .4rem 1rem; border-bottom: 1px solid #1e293b; }}
    .temp {{ color: #fb923c; font-weight: bold; }}
  </style>
</head>
<body>
  <h1>📊 Informe Temperatura DS18B20</h1>
  <p>Període: últims {days} dies — Generat: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
  <div class="stats">
    <div class="stat"><div class="stat-value">{stats.get('min','—')}°C</div><div>Mínima</div></div>
    <div class="stat"><div class="stat-value">{stats.get('max','—')}°C</div><div>Màxima</div></div>
    <div class="stat"><div class="stat-value">{stats.get('avg','—')}°C</div><div>Mitjana</div></div>
    <div class="stat"><div class="stat-value">{stats.get('count','—')}</div><div>Lectures</div></div>
  </div>
  <h2>Últimes 100 lectures</h2>
  <table>
    <tr><th>Data i hora</th><th>Temperatura</th></tr>
    {rows}
  </table>
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML exportat: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Exporta estadístiques de temperatura")
    parser.add_argument("--format", choices=["json", "csv", "html"], default="json")
    parser.add_argument("--days", type=int, default=30, help="Dies a exportar")
    parser.add_argument("--output", type=str, help="Fitxer de sortida (opcional)")
    args = parser.parse_args()

    hours = args.days * 24
    readings = load_recent_readings(hours=hours)
    stats = compute_statistics(readings)

    if not readings:
        print("⚠️  Sense dades per exportar.")
        sys.exit(0)

    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    ext_map = {"json": "json", "csv": "csv", "html": "html"}
    output_path = args.output or str(DATA_DIR / f"export_{now_str}.{ext_map[args.format]}")

    if args.format == "json":
        export_json(readings, stats, output_path)
    elif args.format == "csv":
        export_csv(readings, output_path)
    elif args.format == "html":
        export_html(readings, stats, args.days, output_path)

    print(f"📋 Estadístiques ({args.days} dies):")
    for k, v in stats.items():
        print(f"   {k}: {v}")


if __name__ == "__main__":
    main()
