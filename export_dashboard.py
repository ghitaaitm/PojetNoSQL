"""
Script pour exporter automatiquement les dashboards et visualisations Kibana
Crée des backups en JSON
"""

import requests
import json
import os
from datetime import datetime

# Configuration
KIBANA_URL = "http://localhost:5601"
OUTPUT_DIR = "dashboards"

def ensure_output_dir():
    """Créer le dossier de sortie s'il n'existe pas"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"✓ Dossier '{OUTPUT_DIR}/' créé")

def get_saved_objects(object_type):
    """Récupérer tous les objets sauvegardés d'un type donné"""
    url = f"{KIBANA_URL}/api/saved_objects/_find"
    
    params = {
        "type": object_type,
        "per_page": 1000
    }
    
    headers = {
        "kbn-xsrf": "true"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            objects = data.get('saved_objects', [])
            print(f"✓ {len(objects)} {object_type}(s) trouvé(s)")
            return objects
        else:
            print(f"✗ Erreur récupération {object_type} : {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Erreur : {e}")
        return []

def export_objects(objects, filename):
    """Exporter des objets au format NDJSON"""
    if not objects:
        print(f"⚠ Aucun objet à exporter pour {filename}")
        return False
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            for obj in objects:
                # Format NDJSON : une ligne JSON par objet
                f.write(json.dumps(obj, ensure_ascii=False) + '\n')
        
        print(f"✓ Exporté : {filepath} ({len(objects)} objets)")
        return True
    except Exception as e:
        print(f"✗ Erreur export {filename} : {e}")
        return False

def export_all():
    """Exporter tous les objets Kibana"""
    print("=" * 70)
    print("EXPORT KIBANA - DASHBOARDS & VISUALISATIONS")
    print("=" * 70)
    print()
    
    ensure_output_dir()
    
    # Timestamp pour les noms de fichiers
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Export des différents types d'objets
    exports = [
        ("dashboard", f"dashboards_{timestamp}.ndjson"),
        ("visualization", f"visualizations_{timestamp}.ndjson"),
        ("search", f"searches_{timestamp}.ndjson"),
        ("index-pattern", f"index_patterns_{timestamp}.ndjson"),
    ]
    
    results = {}
    for object_type, filename in exports:
        print(f"\nExport des {object_type}s...")
        objects = get_saved_objects(object_type)
        success = export_objects(objects, filename)
        results[object_type] = success
    
    # Résumé
    print("\n" + "=" * 70)
    print("RÉSUMÉ DE L'EXPORT")
    print("=" * 70)
    
    for object_type, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {object_type}")
    
    print(f"\n📁 Fichiers sauvegardés dans : {OUTPUT_DIR}/")
    print("=" * 70)

def create_backup_all():
    """Créer un backup complet en un seul fichier"""
    print("\n" + "=" * 70)
    print("BACKUP COMPLET")
    print("=" * 70)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(OUTPUT_DIR, f"backup_complete_{timestamp}.ndjson")
    
    all_objects = []
    for object_type in ["dashboard", "visualization", "search", "index-pattern"]:
        objects = get_saved_objects(object_type)
        all_objects.extend(objects)
    
    if all_objects:
        with open(backup_file, 'w', encoding='utf-8') as f:
            for obj in all_objects:
                f.write(json.dumps(obj, ensure_ascii=False) + '\n')
        
        print(f"✓ Backup complet créé : {backup_file}")
        print(f"  {len(all_objects)} objets sauvegardés")
    else:
        print("⚠ Aucun objet à sauvegarder")

def main():
    try:
        export_all()
        create_backup_all()
        
        print("\n💡 POUR RESTAURER :")
        print("   1. Va dans Kibana → Stack Management → Saved Objects")
        print("   2. Clique 'Import'")
        print("   3. Sélectionne le fichier .ndjson")
        print()
    except Exception as e:
        print(f"\n✗ Erreur fatale : {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
