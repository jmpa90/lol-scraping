import pandas as pd
import os
import sys

def main():
    # 1. Obtener la ubicación exacta donde está ESTE script
    # En GitHub será: .../scraper_repo/scripts
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. Construir la ruta hacia el CSV en el OTRO repositorio
    # Lógica: Salir de 'scripts' (..) -> Salir de 'scraper_repo' (..) -> Entrar a 'data_repo' -> 'data' -> archivo
    
    # NOTA: Esta ruta es relativa a donde se ejecuta el script en la nube
    csv_path = os.path.join(script_dir, "..", "..", "data_repo", "data", "players.csv")
    
    # Normalizamos la ruta para evitar errores de sintaxis
    csv_path = os.path.abspath(csv_path)
    
    print(f"[INFO] Script ejecutándose desde: {script_dir}")
    print(f"[INFO] Buscando CSV en: {csv_path}")

    # 3. Verificar si existe
    if not os.path.exists(csv_path):
        print("[ERROR] El archivo players.csv NO fue encontrado.")
        print("Revisa si el paso 'Checkout Data Repo' en el YAML funcionó correctamente.")
        
        # Debug: Mostrar qué carpetas existen en la raíz para entender el error
        workspace_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
        print(f"[DEBUG] Contenido del Workspace ({workspace_dir}):")
        try:
            print(os.listdir(workspace_dir))
            print(f"[DEBUG] Contenido de data_repo/data: {os.listdir(os.path.join(workspace_dir, 'data_repo', 'data'))}")
        except:
            pass
            
        sys.exit(1)

    # 4. Cargar DataFrame
    try:
        df_players = pd.read_csv(csv_path)
        
        print("\n" + "="*40)
        print(f" ÉXITO: Se cargaron {len(df_players)} jugadores")
        print("="*40)
        # Mostramos las columnas para asegurar que leímos bien
        print(df_players.head()) 
        print("="*40)

    except Exception as e:
        print(f"[CRITICAL] Falló la lectura del CSV: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()