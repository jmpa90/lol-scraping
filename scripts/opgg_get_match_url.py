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
    # 1. Location of THIS script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. Location of Players CSV (Sibling Repo)
    # Path: .../scraper_repo/scripts/../../data_repo/data/players.csv
    csv_path = os.path.join(script_dir, "..", "..", "data_repo", "data", "players.csv")
    
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
        # Importante: Definir el user_agent ayuda a evitar bloqueos
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
                
                # --- AQUÍ TOMAMOS LA FOTO ---
                # Guardamos en la carpeta actual del script (scraper_repo)
                screenshot_name = f"debug_{game_name}.png"
                page.screenshot(path=screenshot_name, full_page=True)
                print(f"📸 SCREENSHOT GUARDADO: {screenshot_name}")
                # -----------------------------
                return

            # ... (Resto de tu lógica de extracción si lo encuentra) ...
            
            # (Si quieres ver la foto aunque funcione, puedes descomentar esto:)
            # page.screenshot(path=f"success_{game_name}.png")

        except Exception as e:
            log(f"❌ Error General: {e}")
            page.screenshot(path="error_crash.png") # Foto si crashea
        finally:
            browser.close()