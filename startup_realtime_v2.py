"""
Script de démarrage automatique - VERSION V2 OPTIMISÉE
Lance le Collector et le Worker avec filtrage configurable
Pipeline 100% temps réel avec Elasticsearch 8.11
"""

import subprocess
import time
import logging
import sys
import os
from datetime import datetime
import psutil

# Fix encodage Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('startup_realtime_v2.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================================================
# CONFIGURATION - MODIFIER ICI
# ================================================
FILTER_MODE = os.getenv('FILTER_MODE', 'balanced')  # strict, balanced, permissive


def print_header():
    """Afficher le header"""
    print("\n" + "=" * 70)
    print("🚀 MASTODON ABSA V2 - DÉMARRAGE AUTOMATIQUE")
    print("=" * 70)
    print("\n📋 Ce script lance automatiquement :")
    print("  1. MASTODON COLLECTOR (streaming temps réel)")
    print("  2. ABSA WORKER V2 OPTIMISÉ (filtrage configurable)")
    print("\n⚡ Nouveautés V2 :")
    print("  • Filtrage configurable (strict/balanced/permissive)")
    print("  • Logs détaillés des raisons de filtrage")
    print("  • Statistiques en temps réel améliorées")
    print("  • Support VERB dans les aspects")
    print(f"\n🔧 Mode de filtrage actuel : {FILTER_MODE.upper()}")
    
    filter_descriptions = {
        'strict': '  → Qualité maximale (filtrage ~85-90%)',
        'balanced': '  → Équilibre qualité/volume (filtrage ~70-80%) [RECOMMANDÉ]',
        'permissive': '  → Volume maximal (filtrage ~60-70%)'
    }
    print(filter_descriptions.get(FILTER_MODE, '  → Mode personnalisé'))
    
    print("\n⚠️  Prérequis (doivent DÉJÀ tourner) :")
    print("  • Redis (localhost:6379)")
    print("  • Elasticsearch 8.11 (localhost:9200) - STATUS GREEN")
    print("\n💡 Appuyez sur Ctrl+C pour arrêter proprement")
    print("=" * 70 + "\n")


def check_redis():
    """Vérifier que Redis est accessible"""
    try:
        import redis
        client = redis.from_url('redis://localhost:6379', socket_connect_timeout=2)
        client.ping()
        logger.info("✓ Redis OK")
        return True
    except Exception as e:
        logger.error(f"✗ Redis NOT accessible: {e}")
        logger.error("  → Lance Redis : docker start redis")
        return False


def check_elasticsearch():
    """Vérifier qu'Elasticsearch est GREEN"""
    try:
        import requests
        
        # Test connexion
        response = requests.get('http://localhost:9200', timeout=2)
        if response.status_code != 200:
            logger.error(f"✗ Elasticsearch répond avec code {response.status_code}")
            return False
        
        # Vérifier le statut du cluster
        health_response = requests.get('http://localhost:9200/_cluster/health', timeout=2)
        health = health_response.json()
        
        status = health.get('status', 'unknown')
        if status == 'green':
            logger.info(f"✓ Elasticsearch OK (status: GREEN)")
            return True
        elif status == 'yellow':
            logger.warning(f"⚠ Elasticsearch YELLOW (acceptable pour mono-nœud)")
            return True
        else:
            logger.error(f"✗ Elasticsearch status: {status.upper()}")
            logger.error(f"  Unassigned shards: {health.get('unassigned_shards', 0)}")
            logger.error("  → Répare ES avant de continuer")
            return False
            
    except Exception as e:
        logger.error(f"✗ Elasticsearch NOT accessible: {e}")
        logger.error("  → Lance Elasticsearch : docker start elasticsearch")
        return False


def check_dependencies():
    """Vérifier les dépendances Python"""
    required = {
        'redis': 'redis',
        'requests': 'requests',
        'mastodon': 'Mastodon.py',
        'transformers': 'transformers',
        'torch': 'torch',
        'elasticsearch': 'elasticsearch',
        'spacy': 'spacy'
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        logger.warning(f"⚠ Packages manquants : {', '.join(missing)}")
        logger.warning("  → Install: pip install " + " ".join(missing))
        return False
    
    logger.info("✓ Dépendances Python OK")
    return True


def run_collector():
    """Lancer le Mastodon Collector"""
    logger.info("\n" + "=" * 70)
    logger.info("LANCEMENT MASTODON COLLECTOR")
    logger.info("=" * 70)
    
    # Chercher le fichier collector
    collector_files = [
        'mastodon_stream.py',
        'mastodon_collector.py',
        'collector_mastodon.py'
    ]
    
    collector_file = None
    for f in collector_files:
        if os.path.exists(f):
            collector_file = f
            break
    
    if not collector_file:
        logger.error(f"✗ Fichier collector non trouvé")
        logger.error(f"  Cherché : {', '.join(collector_files)}")
        return None
    
    try:
        python_cmd = 'python' if sys.platform == 'win32' else 'python3'
        
        process = subprocess.Popen(
            [python_cmd, collector_file],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        
        logger.info(f"✓ Collector lancé (PID: {process.pid}, fichier: {collector_file})")
        return process
        
    except Exception as e:
        logger.error(f"✗ Erreur lancement Collector: {e}")
        return None


def run_worker_optimized():
    """Lancer l'ABSA Worker V2 OPTIMISÉ"""
    logger.info("\n" + "=" * 70)
    logger.info("LANCEMENT ABSA WORKER V2 OPTIMISÉ")
    logger.info("=" * 70)
    
    # Attendre que le collector démarre
    time.sleep(3)
    
    # Chercher le fichier worker (priorité à V2)
    worker_files = [
        'worker_absa_optimized_v2.py',  # Version V2 avec filtrage configurable
        'worker_absa_optimized.py',     # Version optimisée ES 8.11
        'absa_worker_realtime.py',
        'worker_absa.py',
        'absa_worker_fixed.py'
    ]
    
    worker_file = None
    for f in worker_files:
        if os.path.exists(f):
            worker_file = f
            break
    
    if not worker_file:
        logger.error(f"✗ Fichier worker non trouvé")
        logger.error(f"  Cherché : {', '.join(worker_files)}")
        return None
    
    # Indiquer quelle version est utilisée
    if 'v2' in worker_file:
        logger.info(f"✓ Utilisation du worker V2 (filtrage {FILTER_MODE.upper()})")
    elif 'optimized' in worker_file:
        logger.info("✓ Utilisation du worker OPTIMISÉ (ES 8.11 compatible)")
    elif 'realtime' in worker_file:
        logger.info("✓ Utilisation du worker TEMPS RÉEL")
    else:
        logger.warning(f"⚠ Worker standard ({worker_file})")
    
    try:
        python_cmd = 'python' if sys.platform == 'win32' else 'python3'
        
        # Passer le mode de filtrage en variable d'environnement
        env = os.environ.copy()
        env['FILTER_MODE'] = FILTER_MODE
        
        process = subprocess.Popen(
            [python_cmd, worker_file],
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        
        logger.info(f"✓ Worker lancé (PID: {process.pid}, fichier: {worker_file})")
        logger.info(f"✓ Mode de filtrage: {FILTER_MODE.upper()}")
        return process
        
    except Exception as e:
        logger.error(f"✗ Erreur lancement Worker: {e}")
        return None


def get_process_stats(process):
    """Récupérer les stats d'un processus"""
    try:
        proc = psutil.Process(process.pid)
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / 1024 / 1024  # MB
        return {'cpu': cpu, 'mem': mem, 'alive': True}
    except:
        return {'cpu': 0, 'mem': 0, 'alive': False}


def get_redis_stats():
    """Récupérer les stats Redis détaillées"""
    try:
        import redis
        r = redis.from_url('redis://localhost:6379', socket_connect_timeout=1)
        queue_size = r.llen('mastodon_queue')
        
        # Obtenir des infos supplémentaires
        info = r.info()
        connected_clients = info.get('connected_clients', 0)
        used_memory_mb = info.get('used_memory', 0) / 1024 / 1024
        
        return {
            'queue_size': queue_size,
            'clients': connected_clients,
            'memory_mb': used_memory_mb,
            'available': True
        }
    except Exception as e:
        logger.warning(f"⚠ Redis stats unavailable: {e}")
        return {'available': False}


def get_elasticsearch_stats():
    """Récupérer les stats Elasticsearch détaillées"""
    try:
        import requests
        
        # Health
        health = requests.get('http://localhost:9200/_cluster/health', timeout=2).json()
        status = health.get('status', 'unknown').upper()
        
        # Stats des indices
        indices_response = requests.get('http://localhost:9200/_cat/indices/mastodon-*?format=json', timeout=2)
        total_docs = 0
        if indices_response.status_code == 200:
            indices = indices_response.json()
            total_docs = sum(int(idx.get('docs.count', 0)) for idx in indices)
        
        return {
            'status': status,
            'total_docs': total_docs,
            'nodes': health.get('number_of_nodes', 0),
            'available': True
        }
    except Exception as e:
        logger.warning(f"⚠ ES stats unavailable: {e}")
        return {'available': False}


def monitor_processes(collector_proc, worker_proc):
    """Monitorer les processus avec stats détaillées"""
    logger.info("\n" + "=" * 70)
    logger.info("MONITORING PIPELINE V2")
    logger.info("=" * 70)
    logger.info(f"Pipeline actif [Mode: {FILTER_MODE.upper()}]")
    logger.info("Logs en temps réel ci-dessous")
    logger.info("Appuyez sur Ctrl+C pour arrêter proprement\n")
    
    iteration = 0
    try:
        while True:
            iteration += 1
            
            # Vérifier que les processus tournent
            collector_alive = collector_proc and collector_proc.poll() is None
            worker_alive = worker_proc and worker_proc.poll() is None
            
            # Stats toutes les minutes
            if iteration % 6 == 0:
                logger.info("\n" + "=" * 70)
                logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] STATS PIPELINE V2")
                logger.info("=" * 70)
                
                # Stats des processus
                if collector_alive:
                    stats = get_process_stats(collector_proc)
                    logger.info(f"✓ Collector UP  - CPU: {stats['cpu']:.1f}% | RAM: {stats['mem']:.1f} MB")
                else:
                    logger.error("✗ Collector DOWN")
                
                if worker_alive:
                    stats = get_process_stats(worker_proc)
                    logger.info(f"✓ Worker UP     - CPU: {stats['cpu']:.1f}% | RAM: {stats['mem']:.1f} MB | Mode: {FILTER_MODE.upper()}")
                else:
                    logger.error("✗ Worker DOWN")
                
                # Stats Redis détaillées
                redis_stats = get_redis_stats()
                if redis_stats['available']:
                    logger.info(f"📊 Redis        - Queue: {redis_stats['queue_size']} toots | "
                               f"Clients: {redis_stats['clients']} | "
                               f"RAM: {redis_stats['memory_mb']:.1f} MB")
                else:
                    logger.warning("⚠ Redis stats unavailable")
                
                # Stats Elasticsearch détaillées
                es_stats = get_elasticsearch_stats()
                if es_stats['available']:
                    logger.info(f"📊 Elasticsearch - Status: {es_stats['status']} | "
                               f"Docs: {es_stats['total_docs']:,} | "
                               f"Nodes: {es_stats['nodes']}")
                else:
                    logger.warning("⚠ ES stats unavailable")
                
                logger.info("=" * 70 + "\n")
            
            # Relancer si mort
            if not collector_alive and collector_proc:
                logger.error("\n✗ COLLECTOR ARRÊTÉ - Relancement...")
                collector_proc = run_collector()
            
            if not worker_alive and worker_proc:
                logger.error("\n✗ WORKER ARRÊTÉ - Relancement...")
                worker_proc = run_worker_optimized()
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 70)
        logger.info("ARRÊT DEMANDÉ (Ctrl+C)")
        logger.info("=" * 70)
        
        # Terminer proprement
        for name, proc in [("Collector", collector_proc), ("Worker", worker_proc)]:
            if proc and proc.poll() is None:
                logger.info(f"Arrêt {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                    logger.info(f"✓ {name} arrêté")
                except subprocess.TimeoutExpired:
                    logger.warning(f"⚠ {name} ne répond pas, force kill...")
                    proc.kill()
        
        logger.info("\n" + "=" * 70)
        logger.info("PIPELINE ARRÊTÉ")
        logger.info("=" * 70)


def main():
    """Fonction principale"""
    print_header()
    
    # Vérifications
    logger.info("Vérification des prérequis...")
    
    if not check_dependencies():
        logger.error("\n✗ Installation des dépendances requise")
        sys.exit(1)
    
    if not check_redis():
        logger.error("\n✗ Redis doit être démarré")
        logger.error("   Commande : docker start redis")
        sys.exit(1)
    
    if not check_elasticsearch():
        logger.error("\n✗ Elasticsearch doit être GREEN ou YELLOW")
        logger.error("   Vérifier : curl http://localhost:9200/_cluster/health")
        sys.exit(1)
    
    logger.info("\n✓ Tous les prérequis sont OK")
    
    # Lancer le pipeline
    logger.info("\n" + "=" * 70)
    logger.info("DÉMARRAGE DU PIPELINE V2")
    logger.info("=" * 70)
    
    collector_proc = run_collector()
    if not collector_proc:
        logger.error("✗ Échec lancement Collector")
        sys.exit(1)
    
    worker_proc = run_worker_optimized()
    if not worker_proc:
        logger.error("✗ Échec lancement Worker")
        if collector_proc:
            collector_proc.terminate()
        sys.exit(1)
    
    # Monitoring
    monitor_processes(collector_proc, worker_proc)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"\n✗ ERREUR FATALE : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)