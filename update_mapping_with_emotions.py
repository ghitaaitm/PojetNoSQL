"""
Mise à jour du mapping Elasticsearch pour supporter le champ 'emotions'
"""

import requests
import json
import sys
import time

ES_URL = "http://localhost:9200"
KIBANA_URL = "http://localhost:5601"
OLD_INDEX = "mastodon-trends-fixed"
NEW_INDEX = "mastodon-trends-fixed-v2"
INDEX_PATTERN_ID = "mastodon-trends-fixed-star"

def create_index_with_emotions():
    """Créer nouvel index avec champ emotions"""
    print("=" * 70)
    print("CRÉATION INDEX AVEC SUPPORT ÉMOTIONS")
    print("=" * 70 + "\n")
    
    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "5s"
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "created_at": {"type": "date"},
                "language": {"type": "keyword"},
                "text": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                },
                "aspects": {"type": "keyword"},
                "sentiment": {
                    "properties": {
                        "label": {"type": "keyword"},
                        "score": {"type": "float"}
                    }
                },
                # NOUVEAU CHAMP : ÉMOTIONS (liste d'objets)
                "emotions": {
                    "type": "nested",
                    "properties": {
                        "emotion": {"type": "keyword"},
                        "score": {"type": "float"}
                    }
                },
                "critical_tone": {
                    "properties": {
                        "tone": {"type": "keyword"},
                        "critical_score": {"type": "float"},
                        "signals": {"type": "keyword"}
                    }
                },
                "metadata": {
                    "properties": {
                        "hashtags": {"type": "keyword"},
                        "author": {"type": "keyword"},
                        "instance": {"type": "keyword"}
                    }
                }
            }
        }
    }
    
    try:
        # Supprimer si existe
        requests.delete(f"{ES_URL}/{NEW_INDEX}", timeout=5)
        time.sleep(1)
        
        # Créer
        response = requests.put(
            f"{ES_URL}/{NEW_INDEX}",
            headers={"Content-Type": "application/json"},
            json=mapping,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✓ Index '{NEW_INDEX}' créé avec support émotions")
            return True
        else:
            print(f"✗ Erreur: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Erreur: {e}")
        return False

def reindex_old_data():
    """Réindexer anciennes données (optionnel)"""
    print("\n" + "=" * 70)
    print("RÉINDEXATION ANCIENNES DONNÉES (optionnel)")
    print("=" * 70 + "\n")
    
    choice = input("Réindexer les anciennes données ? (o/n) : ").lower()
    
    if choice != 'o':
        print("⚠️  Anciennes données ignorées - Seules les nouvelles seront indexées")
        return True
    
    try:
        response = requests.post(
            f"{ES_URL}/_reindex",
            headers={"Content-Type": "application/json"},
            json={
                "source": {"index": OLD_INDEX},
                "dest": {"index": NEW_INDEX}
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ {result.get('total', 0)} documents réindexés")
            return True
        else:
            print(f"⚠️  Erreur réindexation: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  Erreur: {e}")
        return False

def update_index_pattern():
    """Mettre à jour l'Index Pattern pour pointer vers le nouvel index"""
    print("\n" + "=" * 70)
    print("MISE À JOUR INDEX PATTERN KIBANA")
    print("=" * 70 + "\n")
    
    # Supprimer ancien
    try:
        requests.delete(
            f"{KIBANA_URL}/api/saved_objects/index-pattern/{INDEX_PATTERN_ID}",
            headers={"kbn-xsrf": "true"},
            timeout=5
        )
        time.sleep(1)
    except:
        pass
    
    # Créer nouveau pointant vers les 2 indices
    payload = {
        "attributes": {
            "title": f"{OLD_INDEX}*,{NEW_INDEX}*",
            "timeFieldName": "created_at"
        }
    }
    
    try:
        response = requests.post(
            f"{KIBANA_URL}/api/saved_objects/index-pattern/{INDEX_PATTERN_ID}",
            headers={"kbn-xsrf": "true", "Content-Type": "application/json"},
            json=payload,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✓ Index Pattern mis à jour")
            print(f"  Indices : {OLD_INDEX}*, {NEW_INDEX}*")
            return True
        else:
            print(f"✗ Erreur: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Erreur: {e}")
        return False

def update_env_file():
    """Mettre à jour le fichier .env pour utiliser le nouvel index"""
    print("\n" + "=" * 70)
    print("MISE À JOUR FICHIER .env")
    print("=" * 70 + "\n")
    
    try:
        # Lire .env
        with open('.env', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Modifier ES_INDEX_PREFIX
        new_lines = []
        for line in lines:
            if line.startswith('ES_INDEX_PREFIX='):
                new_lines.append(f'ES_INDEX_PREFIX={NEW_INDEX}\n')
            else:
                new_lines.append(line)
        
        # Écrire
        with open('.env', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"✓ .env mis à jour")
        print(f"  ES_INDEX_PREFIX={NEW_INDEX}")
        return True
    except Exception as e:
        print(f"⚠️  Erreur mise à jour .env: {e}")
        print("   Tu devras modifier manuellement ES_INDEX_PREFIX")
        return False

def main():
    print("\n" + "=" * 70)
    print("🔧 MISE À JOUR ELASTICSEARCH POUR ÉMOTIONS")
    print("=" * 70)
    print("\nCe script va :")
    print("  1. Créer un nouvel index avec support du champ 'emotions'")
    print("  2. Optionnellement réindexer les anciennes données")
    print("  3. Mettre à jour l'Index Pattern Kibana")
    print("  4. Mettre à jour le fichier .env")
    print("\n⚠️  Le nouveau worker devra indexer dans ce nouvel index\n")
    
    input("Appuie sur Entrée pour continuer...")
    
    # Étapes
    if not create_index_with_emotions():
        print("\n✗ Échec création index")
        sys.exit(1)
    
    time.sleep(2)
    
    reindex_old_data()
    time.sleep(2)
    
    if not update_index_pattern():
        print("\n✗ Échec mise à jour Index Pattern")
        sys.exit(1)
    
    time.sleep(1)
    
    update_env_file()
    
    print("\n" + "=" * 70)
    print("✅ MISE À JOUR TERMINÉE")
    print("=" * 70)
    print(f"\n📋 Prochaines étapes :")
    print(f"  1. Relance le worker : python startup_realtime_v2.py")
    print(f"  2. Attends 10-15 minutes pour collecter de nouvelles données")
    print(f"  3. Lance : python create_final_dashboard_with_emotions.py")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✗ Annulé")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
