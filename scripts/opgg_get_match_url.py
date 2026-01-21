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
# CONFIGURACIÓN DE RUTAS (Tu código que ya funciona)
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

def human_sleep():
    time.sleep(random.uniform(1.0, 2.0))

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
            headless=True,
            args=["--window-size=1920,1080", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US", # Forzamos inglés para asegurar que el texto coincida
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Truco anti-bot extra
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        try:
            log("Navegando...")
            page.goto(opgg_url, wait_until="domcontentloaded", timeout=60000)
            human_sleep()

            # --- NUEVO: INTENTAR CERRAR COOKIES / ADS ---
            try:
                # Intentar cerrar el banner de cookies si aparece (común en Europa/USA)
                accept_cookies = page.get_by_role("button", name="Accept All")
                if accept_cookies.is_visible():
                    log("🍪 Aceptando cookies para limpiar pantalla...")
                    accept_cookies.click()
                    human_sleep()
            except:
                pass
            # --------------------------------------------

            log("Esperando lista de partidas...")
            
            # USAMOS LA LÓGICA DE TU CÓDIGO LOCAL (get_by_role)
            # En lugar de buscar un texto suelto, buscamos el botón accesible
            try:
                # Esperamos a que aparezca AL MENOS UNO de los botones de detalle
                page.get_by_role("button", name="Show More Detail Games").first.wait_for(timeout=15000)
                log("✅ Botones encontrados (Método Local).")
            except Exception as e:
                log(f"❌ No se encontraron botones con el nombre exacto. Error: {e}")
                
                # DEBUG: Imprimir qué botones SÍ ve Playwright
                log("🔍 LISTANDO TODOS LOS BOTONES VISIBLES PARA DEBUG:")
                all_buttons = page.get_by_role("button").all()
                for btn in all_buttons[:10]: # Solo los primeros 10 para no spamear
                    try:
                        txt = btn.inner_text().replace('\n', ' ')
                        name = btn.get_attribute("aria-label") or "Sin Label"
                        print(f"   - Texto: '{txt}' | Label: '{name}'")
                    except: pass

                log("📸 Tomando foto del fallo...")
                page.screenshot(path="debug_failed_buttons.png", full_page=True)
                return

            # Si llegamos aquí, encontramos los botones
            buttons = page.get_by_role("button", name="Show More Detail Games")
            count = buttons.count()
            log(f"Partidas encontradas: {count}")

            if count > 0:
                log("Procesando la PRIMERA partida...")
                btn = buttons.first
                
                # Scroll para asegurar que el ad no lo tapa
                btn.scroll_into_view_if_needed()
                human_sleep()
                
                # Intentar clic (con force=True por si un ad lo tapa parcialmente)
                btn.click(force=True)
                human_sleep()
                
                # Obtener URL
                try:
                    url_input = page.locator("input.link").last
                    match_url = url_input.get_attribute("value")
                    print(f"\n🎉 ¡ÉXITO! URL OBTENIDA: {match_url}")
                except:
                    log("❌ Se hizo clic, pero no apareció el input con la URL.")
                    page.screenshot(path="debug_click_fail.png")

            else:
                log("⚠️ El contador de botones es 0.")

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