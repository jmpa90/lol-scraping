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

# === GOOGLE IMPORTS ===
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaFileUpload

# ... (imports anteriores se mantienen) ...

# === GOOGLE IMPORTS ===
# CAMBIO 1: Importar service_account en lugar de usar Credentials genérico de usuario
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================

# ⚠️ TU FOLDER ID
DRIVE_FOLDER_ID = "1vTF3GwgMyjzF4OcaJtpSNz9ezyG0htaJ" 

SCOPES = ["https://www.googleapis.com/auth/drive"]

def setup_paths():
    print("--- [SETUP] Configurando rutas... ---")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
    csv_path = os.path.join(workspace_dir, "data_repo", "data", "players.csv")
    return os.path.abspath(csv_path)

CSV_PATH = setup_paths()

# # ==========================================
# # 2. UTILIDADES DE DRIVE
# # ==========================================
# def get_drive_service():
#     """Autentica y devuelve el servicio de Drive."""
#     token_json = os.environ.get("GOOGLE_DRIVE_TOKEN")
#     if not token_json:
#         print("❌ [DRIVE] No se encontró la variable GOOGLE_DRIVE_TOKEN")
#         return None
    
#     try:
#         creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
#         return build("drive", "v3", credentials=creds)
#     except Exception as e:
#         print(f"❌ [DRIVE] Error de autenticación: {e}")
#         return None

# ==========================================
# 2. UTILIDADES DE DRIVE
# ==========================================
def get_drive_service():
    """Autentica y devuelve el servicio de Drive usando Service Account."""
    
    # CAMBIO 2: Buscar la variable GCP_SERVICE_ACCOUNT
    sa_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    if not sa_json:
        print("❌ [DRIVE] No se encontró la variable GCP_SERVICE_ACCOUNT")
        return None
    
    try:
        # CAMBIO 3: Cargar credenciales de cuenta de servicio
        sa_info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"❌ [DRIVE] Error de autenticación con Service Account: {e}")
        return None



def upload_json_to_drive(service, match_data):
    """Guarda un dict como JSON temporal y lo sube a Drive."""
    if not service:
        return

    # Limpieza de nombre segura
    safe_name = re.sub(r'[^\w\-]', '_', match_data['opgg_url'])
    file_name = f"{safe_name}.json"
    
    # Crear archivo temporal localmente
    temp_path = file_name
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(match_data, f, indent=2, ensure_ascii=False)

    try:
        # 1. Buscar si ya existe
        query = f"name='{file_name}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files_in_drive = results.get("files", [])

        media = MediaFileUpload(temp_path, mimetype='application/json', resumable=False)

        if files_in_drive:
            # ACTUALIZAR
            file_id = files_in_drive[0]["id"]
            updated_file = service.files().update(
                fileId=file_id,
                media_body=media,
                fields="id,name"
            ).execute()
            print(f"☁️ [DRIVE] Actualizado: {file_name} (ID: {updated_file['id']})")
        else:
            # CREAR NUEVO
            file_metadata = {"name": file_name, "parents": [DRIVE_FOLDER_ID]}
            created_file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id,name"
            ).execute()
            print(f"☁️ [DRIVE] Subido: {file_name} (ID: {created_file['id']})")

    except Exception as e:
        print(f"❌ [DRIVE] Error subiendo archivo: {e}")
    finally:
        # Limpieza: Borrar archivo temporal local
        if os.path.exists(temp_path):
            os.remove(temp_path)

# ==========================================
# 3. UTILIDADES DE SCRAPING
# ==========================================
def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

def human_sleep(min_s=1.0, max_s=2.0):
    time.sleep(random.uniform(min_s, max_s))

def played_at_to_timestamp_ms(played_at_str: str) -> int:
    try:
        dt = datetime.strptime(played_at_str, "%m/%d/%Y, %I:%M %p")
        dt_utc = dt.replace(tzinfo=timezone.utc)
        return int(dt_utc.timestamp() * 1000)
    except Exception:
        return 0

def parse_match_raw_text(raw_text: str, player_name: str) -> dict:
    """Extrae datos básicos del texto crudo de la tarjeta"""
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    data = {}
    
    # Queue (a veces la primera línea)
    if lines:
        data["queue"] = lines[0]

    # Resultado
    for l in lines:
        if l in ("Victory", "Defeat", "Remake"):
            data["result"] = l
            break

    # Duración
    for l in lines:
        if re.match(r"\d+m \d+s", l):
            data["duration"] = l
            break

    # KDA
    kda_match = re.search(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", raw_text)
    if kda_match:
        data["kills"] = int(kda_match.group(1))
        data["deaths"] = int(kda_match.group(2))
        data["assists"] = int(kda_match.group(3))

    # Champion
    try:
        # Búsqueda simple basada en que el campeón suele estar cerca del nombre
        data["champion"] = "Unknown" 
    except ValueError:
        data["champion"] = None

    return data

# ==========================================
# 4. LÓGICA DE SCRAPING PRINCIPAL
# ==========================================
def scrape_player(service, game_name: str, tagline: str):
    player_id = f"{quote(game_name)}-{tagline}"
    opgg_url = f"https://op.gg/lol/summoners/kr/{player_id}?queue_type=SOLORANKED"
    
    print("\n" + "="*60)
    print(f"🚀 PROCESANDO: {game_name} #{tagline}")
    print(f"🔗 URL: {opgg_url}")
    print("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            # args=["--window-size=1920,1080", "--disable-blink-features=AutomationControlled"]
            args=[
                "--window-size=1920,1080", 
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",             # <--- AGREGAR ESTO
                "--disable-setuid-sandbox"  # <--- Y ESTO
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        try:
            log(f"Navegando...", "NET")
            page.goto(opgg_url, wait_until="domcontentloaded", timeout=60000)
            human_sleep(2, 3)

            try: page.get_by_role("button", name="Accept All").click(timeout=3000)
            except: pass

            # === REVERSIÓN A LA ESTRATEGIA QUE FUNCIONA (Get By Role) ===
            try: 
                page.get_by_role("button", name="Show More Detail Games").first.wait_for(timeout=20000)
            except:
                log(f"No se encontraron partidas.", "WARN")
                return

            buttons = page.get_by_role("button", name="Show More Detail Games")
            total = buttons.count()
            log(f"Partidas encontradas: {total}", "INFO")

            limit = 100 
            for i in range(min(total, limit)): 
                try:
                    btn = buttons.nth(i)
                    btn.scroll_into_view_if_needed()
                    human_sleep(0.3, 0.6)
                    
                    # === ESTRATEGIA DE TU LOCAL (XPath Robusto) ===
                    # Busca el ancestro que contiene "Ranked Solo/Duo" y el botón.
                    # Esto garantiza que estamos en la tarjeta correcta.
                    match_card = btn.locator(
                        "xpath=ancestor::*[.//text()[contains(., 'Ranked Solo/Duo')] "
                        "and .//button[contains(., 'Show More Detail Games')]][1]"
                    )
                    
                    # Extraer texto previo
                    raw_text = "No Text"
                    try:
                        raw_text = match_card.inner_text(timeout=2000)
                    except: pass

                    played_at_str = "Unknown"
                    try:
                        played_at_str = match_card.locator("span[data-tooltip-content]").first.get_attribute("data-tooltip-content")
                    except: pass
                    
                    played_at_ts = played_at_to_timestamp_ms(played_at_str)

                    # Expandir
                    btn.click(force=True)
                    human_sleep(1.0, 1.5)

                    # Extraer URL (Estrategia Last Textbox)
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

                        # ========================================
                        # SUBIDA A DRIVE
                        # ========================================
                        print(f"📤 Preparando subida para: {match_url[-15:]}...")
                        upload_json_to_drive(service, final_data)
                        # ========================================
                    
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
# 5. EJECUCIÓN PRINCIPAL
# ==========================================
if __name__ == "__main__":
    if not os.path.exists(CSV_PATH):
        log(f"CSV no encontrado en {CSV_PATH}", "CRITICAL")
        sys.exit(1)

    # Inicializar Drive UNA VEZ
    drive_service = get_drive_service()
    if not drive_service:
        log("No se pudo iniciar el servicio de Drive. Abortando.", "CRITICAL")
        sys.exit(1)

    try:
        df = pd.read_csv(CSV_PATH)
        log(f"Cargados {len(df)} jugadores del CSV.", "INIT")
        
        # YA NO HAY FILTRO iloc[:1] -> PROCESA TODOS
        
        for index, row in df.iterrows():
            g_name = row["riotIdGameName"]
            tagline = row["riotIdTagline"]
            scrape_player(drive_service, g_name, tagline)
            
            # Importante: Mantener la pausa para evitar bloqueos masivos
            human_sleep(5, 10) 
            
    except Exception as e:
        log(f"Fallo fatal: {e}", "CRITICAL")
        sys.exit(1)
