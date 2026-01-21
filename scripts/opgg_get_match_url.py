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
# SCRAPER LOGIC
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
            headless=True, # Obligatorio en GitHub Actions
            args=["--window-size=1920,1080", "--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        try:
            log("Navegando...")
            page.goto(opgg_url, wait_until="domcontentloaded", timeout=60000)
            human_sleep()

            # Buscar botón "Show More"
            show_more_sel = "button:has-text('Show More Detail Games')"
            try:
                page.wait_for_selector(show_more_sel, timeout=15000)
                log("✅ Perfil cargado correctamente.")
            except:
                log("❌ No se encontró el botón 'Show More'. Posible bloqueo o perfil vacío.")
                return

            buttons = page.locator(show_more_sel)
            count = buttons.count()
            log(f"Partidas encontradas: {count}")

            if count > 0:
                log("Extrayendo la PRIMERA partida...")
                
                # Click en la primera partida
                btn = buttons.first
                btn.click()
                human_sleep()
                
                # Obtener URL
                url_input = page.locator("input.link").last
                match_url = url_input.get_attribute("value")
                
                # Obtener Datos básicos
                card = btn.locator("xpath=ancestor::li").first
                if not card.count(): card = btn.locator("xpath=ancestor::div[contains(@class, 'GameItem')]").first
                
                raw_text = card.inner_text()
                parsed_data = parse_match_details(raw_text)

                # === RESULTADO FINAL ===
                result = {
                    "player": game_name,
                    "match_url": match_url,
                    "details": parsed_data
                }
                
                print("\n" + "★"*20 + " RESULTADO OBTENIDO " + "★"*20)
                print(json.dumps(result, indent=4)) # <--- ESTO ES LO QUE VERÁS EN LOGS
                print("★"*60 + "\n")

            else:
                log("No hay partidas para mostrar.")
                
        except Exception as e:
            log(f"❌ Error: {e}")
        finally:
            browser.close()

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    if not os.path.exists(CSV_PATH):
        log(f"Error Crítico: No se encuentra el CSV en {CSV_PATH}")
        sys.exit(1)

    try:
        df = pd.read_csv(CSV_PATH)
        # Solo tomamos el PRIMER jugador para la prueba
        first_row = df.iloc[0]
        scrape_single_test(first_row["riotIdGameName"], first_row["riotIdTagline"])
            
    except Exception as e:
        log(f"Error Fatal: {e}")
        sys.exit(1)