from playwright.sync_api import sync_playwright
import pandas as pd
import time
import random
import json
import os
import sys
import re
from urllib.parse import quote

# ==========================================
# PATH CONFIGURATION
# ==========================================

def setup_paths():
    print("--- [DEBUG] Iniciando configuración de rutas ---")
    
    # 1. Dónde está ESTE script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"📍 Script directory: {script_dir}")

    # 2. Intentamos localizar el CSV
    # Estructura esperada en GitHub Actions:
    # workspace/scraper_repo/scripts/opgg_get_match_url.py  <-- Estamos aquí
    # workspace/data_repo/data/players.csv                 <-- Queremos ir aquí
    
    # Subimos 2 niveles: scripts -> scraper_repo -> workspace
    workspace_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
    csv_path = os.path.join(workspace_dir, "data_repo", "data", "players.csv")
    
    print(f"🔍 Buscando CSV en: {csv_path}")
    
    # DIAGNÓSTICO: Si no existe, mostrar qué hay en la carpeta 'data_repo'
    if not os.path.exists(csv_path):
        print("❌ EL CSV NO APARECE. Diagnóstico de carpetas:")
        data_repo_path = os.path.join(workspace_dir, "data_repo")
        if os.path.exists(data_repo_path):
            print(f"📂 Contenido de {data_repo_path}:")
            try:
                for root, dirs, files in os.walk(data_repo_path):
                    print(f"   {root}/")
                    for f in files:
                        print(f"     - {f}")
            except Exception as e:
                print(f"Error listando carpetas: {e}")
        else:
            print(f"⚠️ La carpeta {data_repo_path} NO EXISTE. Revisa el YAML.")
            
    return os.path.abspath(csv_path)

CSV_PATH = setup_paths()

# ==========================================
# UTILS
# ==========================================

def log(msg):
    print(f"[INFO] {msg}")

def human_sleep():
    time.sleep(random.uniform(1.0, 2.0))

def parse_match_details(raw_text: str) -> dict:
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    data = {}
    if not lines: return data
    
    data["queue"] = lines[0]
    for l in lines:
        if l in ("Victory", "Defeat"):
            data["result"] = l
            break
    return data

# ==========================================
# SCRAPER LOGIC CON SCREENSHOT
# ==========================================

def scrape_single_test(game_name: str, tagline: str):
    player_id = f"{quote(game_name)}-{tagline}"
    opgg_url = f"https://op.gg/lol/summoners/kr/{player_id}?queue_type=SOLORANKED"
    
    print("\n" + "="*50)
    print(f"🚀 INICIANDO TEST PARA: {game_name} #{tagline}")
    print(f"🔗 URL: {opgg_url}")
    print("="*50)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--window-size=1920,1080", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            log("Navegando...")
            page.goto(opgg_url, wait_until="domcontentloaded", timeout=60000)
            human_sleep()

            # Buscar botón "Show More"
            show_more_sel = "button:has-text('Show More Detail Games')"
            
            try:
                page.wait_for_selector(show_more_sel, timeout=10000)
                log("✅ Perfil cargado correctamente.")
            except:
                log("❌ No se encontró el botón. Tomando captura de pantalla...")
                screenshot_name = f"debug_{game_name}.png"
                page.screenshot(path=screenshot_name, full_page=True)
                print(f"📸 SCREENSHOT GUARDADO: {screenshot_name}")
                return

            buttons = page.locator(show_more_sel)
            count = buttons.count()
            log(f"Partidas encontradas: {count}")
            
            # (Opcional) Guardar pantallazo de éxito también
            # page.screenshot(path="success.png")

        except Exception as e:
            log(f"❌ Error General: {e}")
            page.screenshot(path="error_crash.png")
        finally:
            browser.close()

# ==========================================
# MAIN EXECUTION (ESTO FALTABA)
# ==========================================

if __name__ == "__main__":
    print("🟢 Script iniciado.")
    
    if not os.path.exists(CSV_PATH):
        print(f"🔴 ERROR FATAL: No se encontró el CSV en {CSV_PATH}")
        sys.exit(1)

    try:
        print(f"📖 Leyendo CSV...")
        df = pd.read_csv(CSV_PATH)
        print(f"✅ CSV cargado. {len(df)} filas.")
        
        if not df.empty:
            first_row = df.iloc[0]
            # Aseguramos que las columnas existen
            if "riotIdGameName" in df.columns and "riotIdTagline" in df.columns:
                scrape_single_test(first_row["riotIdGameName"], first_row["riotIdTagline"])
            else:
                print(f"⚠️ Columnas incorrectas en CSV. Encontradas: {df.columns.tolist()}")
        else:
            print("⚠️ El CSV está vacío.")
            
    except Exception as e:
        print(f"🔴 Error Fatal en Main: {e}")
        sys.exit(1)