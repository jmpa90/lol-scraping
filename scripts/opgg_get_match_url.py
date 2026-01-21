from playwright.sync_api import sync_playwright
import pandas as pd
import time
import random
import os
import sys
from urllib.parse import quote

# ==========================================
# CONFIGURACIÓN DE RUTAS (INFRAESTRUCTURA GITHUB)
# ==========================================
def setup_paths():
    print("--- [DEBUG] Iniciando configuración de rutas ---")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
    csv_path = os.path.join(workspace_dir, "data_repo", "data", "players.csv")
    return os.path.abspath(csv_path)

CSV_PATH = setup_paths()

# ==========================================
# UTILS
# ==========================================
def log(msg):
    print(f"[INFO] {msg}")

def human_sleep(min_s=1.0, max_s=2.0):
    time.sleep(random.uniform(min_s, max_s))

# ==========================================
# SCRAPER LOGIC (LÓGICA LOCAL ADAPTADA)
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
            locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        try:
            log("Navegando...")
            page.goto(opgg_url, wait_until="domcontentloaded", timeout=60000)
            human_sleep(2, 3)

            # Intentar cerrar cookies (Best effort)
            try:
                page.get_by_role("button", name="Accept All").click(timeout=2000)
            except: pass

            log("Buscando botones 'Show More Detail Games'...")
            
            # Usamos get_by_role como en tu script local
            try:
                page.get_by_role("button", name="Show More Detail Games").first.wait_for(timeout=20000)
            except:
                log("❌ No se encontraron botones.")
                page.screenshot(path="debug_no_buttons.png")
                return

            buttons = page.get_by_role("button", name="Show More Detail Games")
            count = buttons.count()
            log(f"✅ Partidas encontradas: {count}")

            if count > 0:
                log("Procesando la PRIMERA partida...")
                btn = buttons.first
                btn.scroll_into_view_if_needed()
                
                # Clic forzado (útil para GitHub Actions con Ads)
                log("Haciendo Click...")
                btn.click(force=True)
                
                # --- LA CLAVE DE TU SCRIPT LOCAL ---
                log("⏳ Esperando un momento a que aparezca el textbox...")
                human_sleep(1.5, 2.5) # Damos tiempo a la UI
                
                log("🎣 Intentando obtener el ÚLTIMO textbox de toda la página...")
                
                try:
                    # ESTRATEGIA ORIGINAL LOCAL:
                    # Buscamos TODOS los textboxes y tomamos el ÚLTIMO (.last)
                    # Esto evita tener que buscar dentro de un contenedor específico
                    target_input = page.get_by_role("textbox").last
                    
                    # Esperamos que esté listo (por seguridad)
                    target_input.wait_for(state="attached", timeout=5000)
                    
                    match_url = target_input.get_attribute("value")
                    
                    if match_url:
                        print(f"\n🎉 ¡ÉXITO TOTAL! URL OBTENIDA: {match_url}")
                        page.screenshot(path="success.png")
                    else:
                        log("⚠️ Textbox encontrado pero VALUE vacío.")
                        
                except Exception as e:
                    log(f"❌ Falló la estrategia del último textbox: {e}")
                    page.screenshot(path="debug_textbox_fail.png", full_page=True)

            else:
                log("⚠️ 0 Partidas encontradas.")

        except Exception as e:
            log(f"❌ Error Crítico: {e}")
            page.screenshot(path="error_crash.png")
        finally:
            browser.close()

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    if not os.path.exists(CSV_PATH):
        print(f"🔴 ERROR FATAL: No se encontró el CSV en {CSV_PATH}")
        sys.exit(1)

    try:
        df = pd.read_csv(CSV_PATH)
        if not df.empty:
            first_row = df.iloc[0]
            scrape_single_test(first_row["riotIdGameName"], first_row["riotIdTagline"])
    except Exception as e:
        print(f"🔴 Error Main: {e}")
        sys.exit(1)