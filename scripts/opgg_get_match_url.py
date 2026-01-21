from playwright.sync_api import sync_playwright
import pandas as pd
import time
import random
import json
import os
import sys
import re
from datetime import datetime, timezone
from urllib.parse import quote

# ==========================================
# 1. CONFIGURACIÓN DE RUTAS (GitHub Actions)
# ==========================================
def setup_paths():
    print("--- [SETUP] Configurando rutas... ---")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
    csv_path = os.path.join(workspace_dir, "data_repo", "data", "players.csv")
    return os.path.abspath(csv_path)

CSV_PATH = setup_paths()

# ==========================================
# 2. UTILIDADES (De tu script local)
# ==========================================
def log(msg, level="INFO"):
    # Usamos print simple para evitar problemas de encoding en logs de Linux
    print(f"[{level}] {msg}")

def human_sleep(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))

def parse_match_raw_text(raw_text: str, player_name: str) -> dict:
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    data = {}

    # A veces la primera línea no es la cola si hay banners, pero confiamos en tu lógica local
    if lines:
        data["queue"] = lines[0]

    for l in lines:
        if l in ("Victory", "Defeat", "Remake"):
            data["result"] = l
            break

    for l in lines:
        if re.match(r"\d+m \d+s", l):
            data["duration"] = l
            break

    kda_match = re.search(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", raw_text)
    if kda_match:
        data["kills"] = int(kda_match.group(1))
        data["deaths"] = int(kda_match.group(2))
        data["assists"] = int(kda_match.group(3))

    try:
        # Búsqueda simple del campeón basada en el nombre del jugador
        if player_name in lines:
            idx = lines.index(player_name)
            if idx > 0:
                data["champion"] = lines[idx - 1]
    except ValueError:
        data["champion"] = None

    return data

def played_at_to_timestamp_ms(played_at_str: str) -> int:
    try:
        dt = datetime.strptime(played_at_str, "%m/%d/%Y, %I:%M %p")
        dt_utc = dt.replace(tzinfo=timezone.utc)
        return int(dt_utc.timestamp() * 1000)
    except Exception as e:
        return 0

# ==========================================
# 3. LÓGICA DE SCRAPING
# ==========================================
def scrape_player(game_name: str, tagline: str):
    player_id = f"{quote(game_name)}-{tagline}"
    opgg_url = f"https://op.gg/lol/summoners/kr/{player_id}?queue_type=SOLORANKED"
    
    print("\n" + "="*60)
    print(f"🚀 PROCESANDO: {game_name} #{tagline}")
    print(f"🔗 URL: {opgg_url}")
    print("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--window-size=1920,1080", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US", # Forzamos EN-US para coincidir con tu lógica de fechas
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        try:
            log(f"Navegando...", "NET")
            page.goto(opgg_url, wait_until="domcontentloaded", timeout=60000)
            human_sleep(2, 3)

            try:
                page.get_by_role("button", name="Accept All").click(timeout=3000)
            except: pass

            try:
                page.get_by_role("button", name="Show More Detail Games").first.wait_for(timeout=20000)
            except:
                log(f"No se encontraron partidas.", "WARN")
                return

            buttons = page.get_by_role("button", name="Show More Detail Games")
            total = buttons.count()
            log(f"Partidas encontradas: {total}", "INFO")

            # Limitamos a 3 para la prueba en GitHub Actions
            limit = 3 
            for i in range(min(total, limit)): 
                try:
                    # 1. Obtenemos el botón específico
                    btn = buttons.nth(i)
                    btn.scroll_into_view_if_needed()
                    human_sleep(0.3, 0.6)

                    # 2. DEFINICIÓN DE LA TARJETA (Tu lógica Local Exacta)
                    # Busca el ancestro que contiene texto "Ranked Solo/Duo" y el botón "Show More"
                    # Esto asegura que estamos en la tarjeta correcta.
                    match_card = btn.locator(
                        "xpath=ancestor::*[.//text()[contains(., 'Ranked Solo/Duo')] "
                        "and .//button[contains(., 'Show More Detail Games')]][1]"
                    )

                    # 3. Extraer Texto y Fecha (ANTES de expandir, más seguro)
                    raw_text = match_card.inner_text()
                    
                    played_at_str = "Unknown"
                    try:
                        time_span = match_card.locator("span[data-tooltip-content]").first
                        played_at_str = time_span.get_attribute("data-tooltip-content")
                    except: pass
                    
                    played_at_ts = played_at_to_timestamp_ms(played_at_str)

                    # 4. Expandir para sacar la URL
                    btn.click(force=True)
                    human_sleep(1.0, 1.5)

                    # 5. Obtener URL (Estrategia .last textbox)
                    target_input = page.get_by_role("textbox").last
                    match_url = ""
                    
                    try:
                        target_input.wait_for(state="attached", timeout=5000)
                        match_url = target_input.get_attribute("value")
                    except:
                        log(f"No se pudo extraer URL partida {i+1}", "WARN")
                        btn.click(force=True)
                        continue

                    if match_url:
                        parsed_data = parse_match_raw_text(raw_text, game_name)
                        
                        final_data = {
                            "player_name": game_name,
                            "player_tag": tagline,
                            "opgg_url": match_url,
                            "played_at": played_at_str,
                            "played_at_timestamp": played_at_ts,
                            **parsed_data,
                            "scraped_at": datetime.utcnow().isoformat()
                        }

                        print("\n" + "-"*30)
                        print(f"✅ DATOS EXTRAÍDOS (Partida {i+1}):")
                        print(json.dumps(final_data, indent=2, ensure_ascii=False))
                        print("-"*30 + "\n")
                    
                    # Cerrar detalle
                    btn.click(force=True)
                    human_sleep(0.3, 0.6)

                except Exception as e:
                    log(f"Error en partida {i+1}: {e}", "ERROR")
                    continue

        except Exception as e:
            log(f"Error general: {e}", "ERROR")
        finally:
            browser.close()

# ==========================================
# 4. EJECUCIÓN PRINCIPAL
# ==========================================
if __name__ == "__main__":
    if not os.path.exists(CSV_PATH):
        log(f"CSV no encontrado en {CSV_PATH}", "CRITICAL")
        sys.exit(1)

    try:
        df = pd.read_csv(CSV_PATH)
        log(f"Cargados {len(df)} jugadores del CSV.", "INIT")
        
        # MODO TEST: SOLO 1 JUGADOR
        if not df.empty:
            log("⚠️ MODO TEST ACTIVADO: Procesando SOLO el primer jugador.", "TEST")
            df = df.iloc[:1] 
        
        for index, row in df.iterrows():
            g_name = row["riotIdGameName"]
            tagline = row["riotIdTagline"]
            scrape_player(g_name, tagline)
            
    except Exception as e:
        log(f"Fallo fatal: {e}", "CRITICAL")
        sys.exit(1)