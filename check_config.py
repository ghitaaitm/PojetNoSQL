"""
Script de vérification de la configuration
Vérifie que tout est bien configuré avant de démarrer
"""

import os
import sys
from pathlib import Path

def print_header():
    print("\n" + "=" * 70)
    print("🔍 VÉRIFICATION DE LA CONFIGURATION")
    print("=" * 70 + "\n")


def check_env_file():
    """Vérifier que le fichier .env existe et contient les variables requises"""
    print("📄 Fichier .env")
    print("-" * 70)
    
    if not Path('.env').exists():
        print("❌ ERREUR : Fichier .env introuvable")
        print("   → Créez-le en copiant env.example")
        print("   → Ou lancez : python configure_filter_mode.py")
        return False
    
    print("✓ Fichier .env existe")
    
    # Lire et parser le .env
    env_vars = {}
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    # Variables requises
    required = {
        'MASTODON_INSTANCE_URL': 'Instance Mastodon',
        'MASTODON_ACCESS_TOKEN': 'Token d\'accès Mastodon',
        'REDIS_URL': 'URL Redis',
        'QUEUE_NAME': 'Nom de la queue Redis',
        'ES_HOST': 'Host Elasticsearch',
        'FILTER_MODE': 'Mode de filtrage'
    }
    
    all_ok = True
    for var, description in required.items():
        if var in env_vars and env_vars[var] and not env_vars[var].startswith('#'):
            if var == 'MASTODON_ACCESS_TOKEN':
                masked = env_vars[var][:8] + "..." + env_vars[var][-8:] if len(env_vars[var]) > 16 else "***"
                print(f"✓ {description:30s} : {masked}")
            else:
                print(f"✓ {description:30s} : {env_vars[var]}")
        else:
            print(f"❌ {description:30s} : MANQUANT")
            all_ok = False
    
    print()
    return all_ok


def check_redis():
    """Vérifier que Redis est accessible"""
    print("🗄️  Redis")
    print("-" * 70)
    
    try:
        import redis
        client = redis.from_url('redis://localhost:6379', socket_connect_timeout=2)
        client.ping()
        
        # Stats Redis
        info = client.info()
        print(f"✓ Redis connecté")
        print(f"  Version : {info.get('redis_version', 'N/A')}")
        print(f"  Clients : {info.get('connected_clients', 0)}")
        print(f"  Mémoire : {info.get('used_memory_human', 'N/A')}")
        print()
        return True
    except ImportError:
        print("❌ Module redis non installé")
        print("   → pip install redis")
        print()
        return False
    except Exception as e:
        print(f"❌ Redis inaccessible : {e}")
        print("   → Démarrez Redis : docker start redis")
        print()
        return False


def check_elasticsearch():
    """Vérifier qu'Elasticsearch est accessible"""
    print("🔍 Elasticsearch")
    print("-" * 70)
    
    try:
        import requests
        
        # Connexion
        response = requests.get('http://localhost:9200', timeout=2)
        if response.status_code != 200:
            print(f"❌ Elasticsearch répond avec code {response.status_code}")
            print()
            return False
        
        info = response.json()
        print(f"✓ Elasticsearch connecté")
        print(f"  Version : {info.get('version', {}).get('number', 'N/A')}")
        
        # Health
        health = requests.get('http://localhost:9200/_cluster/health', timeout=2).json()
        status = health.get('status', 'unknown')
        
        if status == 'green':
            print(f"✓ Status : GREEN")
        elif status == 'yellow':
            print(f"⚠️  Status : YELLOW (acceptable mono-nœud)")
        else:
            print(f"❌ Status : {status.upper()}")
            print(f"   Shards non assignés : {health.get('unassigned_shards', 0)}")
            print()
            return False
        
        # Indices
        indices_response = requests.get('http://localhost:9200/_cat/indices/mastodon-*?format=json', timeout=2)
        if indices_response.status_code == 200:
            indices = indices_response.json()
            total_docs = sum(int(idx.get('docs.count', 0)) for idx in indices)
            print(f"  Indices : {len(indices)}")
            print(f"  Documents : {total_docs:,}")
        
        print()
        return status in ['green', 'yellow']
        
    except ImportError:
        print("❌ Module requests non installé")
        print("   → pip install requests")
        print()
        return False
    except Exception as e:
        print(f"❌ Elasticsearch inaccessible : {e}")
        print("   → Démarrez ES : docker start elasticsearch")
        print()
        return False


def check_python_packages():
    """Vérifier les packages Python requis"""
    print("📦 Packages Python")
    print("-" * 70)
    
    required = {
        'redis': 'redis',
        'requests': 'requests',
        'mastodon': 'Mastodon.py',
        'transformers': 'transformers',
        'torch': 'torch',
        'elasticsearch': 'elasticsearch',
        'spacy': 'spacy',
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
            print(f"✓ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)
    
    print()
    
    if missing:
        print(f"⚠️  Packages manquants : {', '.join(missing)}")
        print(f"   → pip install {' '.join(missing)}")
        print()
        return False
    
    return True


def check_worker_files():
    """Vérifier que les fichiers du worker existent"""
    print("📁 Fichiers du pipeline")
    print("-" * 70)
    
    files = {
        'Collector': ['mastodon_stream.py', 'mastodon_collector.py', 'collector_mastodon.py'],
        'Worker V2': ['worker_absa_optimized_v2.py'],
        'Worker (fallback)': ['worker_absa_optimized.py', 'absa_worker_realtime.py', 'worker_absa.py'],
        'Startup': ['startup_realtime_v2.py', 'startup_realtime.py'],
    }
    
    all_ok = True
    for component, filenames in files.items():
        found = None
        for filename in filenames:
            if Path(filename).exists():
                found = filename
                break
        
        if found:
            print(f"✓ {component:20s} : {found}")
        else:
            print(f"❌ {component:20s} : Aucun fichier trouvé")
            print(f"   Cherché : {', '.join(filenames)}")
            all_ok = False
    
    print()
    return all_ok


def main():
    print_header()
    
    checks = {
        'Configuration .env': check_env_file(),
        'Packages Python': check_python_packages(),
        'Fichiers pipeline': check_worker_files(),
        'Redis': check_redis(),
        'Elasticsearch': check_elasticsearch(),
    }
    
    # Résumé
    print("=" * 70)
    print("📊 RÉSUMÉ")
    print("=" * 70)
    
    for name, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {name}")
    
    print()
    
    if all(checks.values()):
        print("🎉 Tout est OK ! Vous pouvez démarrer le pipeline.")
        print("\nCommande :")
        if sys.platform == 'win32':
            print("  python startup_realtime_v2.py")
        else:
            print("  python3 startup_realtime_v2.py")
    else:
        print("⚠️  Certains prérequis ne sont pas satisfaits.")
        print("   Corrigez les erreurs ci-dessus avant de démarrer.")
    
    print("=" * 70 + "\n")
    
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n✗ Vérification interrompue.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Erreur : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)