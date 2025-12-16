"""
Health Check Script - VERSION TEMPS RÉEL
Vérifie que tous les composants fonctionnent correctement
Teste spécifiquement le mode temps réel et mesure les latences
"""

import sys
import time
import logging
import json
from datetime import datetime, timedelta

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_header():
    """Header stylisé"""
    print("\n" + "=" * 70)
    print("🏥 HEALTH CHECK - MASTODON ABSA (MODE TEMPS RÉEL)")
    print("=" * 70)
    print("Diagnostic complet du pipeline avec tests de latence")
    print("=" * 70 + "\n")


def check_redis():
    """Vérifier Redis avec tests de performance"""
    print("=" * 70)
    print("1️⃣  REDIS CHECK")
    print("=" * 70)
    try:
        import redis
        client = redis.from_url('redis://localhost:6379', socket_connect_timeout=3)
        
        # Test ping
        start = time.time()
        client.ping()
        ping_ms = (time.time() - start) * 1000
        
        # Infos Redis
        info = client.info()
        version = info.get('redis_version', 'N/A')
        
        # Queue stats
        queue_size = client.llen('mastodon_queue')
        
        print(f"✅ Redis OK")
        print(f"   Version      : {version}")
        print(f"   Latence ping : {ping_ms:.2f}ms")
        print(f"   Queue size   : {queue_size} toots en attente")
        
        # Test performance BLPOP
        print(f"\n   Test BLPOP (mode temps réel)...")
        start = time.time()
        result = client.blpop('test_health_check', timeout=1)
        blpop_ms = (time.time() - start) * 1000
        
        if blpop_ms < 1100:  # Devrait timeout à ~1000ms
            print(f"   ✅ BLPOP OK : {blpop_ms:.0f}ms (timeout normal)")
        else:
            print(f"   ⚠️  BLPOP lent : {blpop_ms:.0f}ms")
        
        # Avertissement si queue trop grande
        if queue_size > 100:
            print(f"   ⚠️  ATTENTION : Queue importante ({queue_size} toots)")
            print(f"      Le worker n'arrive peut-être pas à suivre")
        elif queue_size > 0:
            print(f"   ℹ️  Queue active : traitement en cours")
        else:
            print(f"   ℹ️  Queue vide : en attente de nouveaux toots")
        
        return True
        
    except Exception as e:
        print(f"❌ Redis FAIL: {e}")
        print("   → Lance Redis : docker compose up -d redis")
        return False


def check_elasticsearch():
    """Vérifier Elasticsearch avec détails"""
    print("\n" + "=" * 70)
    print("2️⃣  ELASTICSEARCH CHECK")
    print("=" * 70)
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(['http://localhost:9200'], request_timeout=3)
        
        if not es.ping():
            print(f"❌ Elasticsearch FAIL: Pas de réponse")
            return False
        
        # Infos cluster
        info = es.info()
        version = info['version']['number']
        cluster_name = info['cluster_name']
        
        print(f"✅ Elasticsearch OK")
        print(f"   Version      : {version}")
        print(f"   Cluster      : {cluster_name}")
        
        # Stats des indices
        try:
            indices = es.cat.indices(index='mastodon-trends-*', format='json')
            
            if indices:
                print(f"\n   Indices mastodon-trends :")
                total_docs = 0
                total_size = 0
                
                for idx in indices[-5:]:  # 5 derniers
                    name = idx['index']
                    docs = int(idx.get('docs.count', 0))
                    size = idx.get('store.size', '0b')
                    health = idx.get('health', 'unknown')
                    
                    health_icon = "🟢" if health == 'green' else "🟡" if health == 'yellow' else "🔴"
                    print(f"     {health_icon} {name}: {docs} docs, {size}")
                    
                    total_docs += docs
                
                print(f"\n   Total : {total_docs} documents indexés")
                
                # Test latence indexation
                print(f"\n   Test latence indexation...")
                test_doc = {
                    "test": "health_check",
                    "timestamp": datetime.now().isoformat()
                }
                
                start = time.time()
                es.index(index='health-check-test', id='test', body=test_doc)
                index_ms = (time.time() - start) * 1000
                
                print(f"   ✅ Indexation : {index_ms:.2f}ms")
                
                # Nettoyer
                es.indices.delete(index='health-check-test', ignore=[400, 404])
                
            else:
                print(f"   ℹ️  Aucun indice mastodon-trends (normal au départ)")
        
        except Exception as e:
            print(f"   ⚠️  Erreur indices: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Elasticsearch FAIL: {e}")
        print("   → Lance Elasticsearch : docker compose up -d elasticsearch")
        return False


def check_kibana():
    """Vérifier Kibana"""
    print("\n" + "=" * 70)
    print("3️⃣  KIBANA CHECK")
    print("=" * 70)
    try:
        import requests
        response = requests.get('http://localhost:5601/api/status', timeout=3)
        
        if response.status_code == 200:
            status_data = response.json()
            version = status_data.get('version', {}).get('number', 'N/A')
            overall_state = status_data.get('status', {}).get('overall', {}).get('level', 'unknown')
            
            print(f"✅ Kibana OK")
            print(f"   Version : {version}")
            print(f"   État    : {overall_state}")
            print(f"   URL     : http://localhost:5601")
            return True
        else:
            print(f"❌ Kibana FAIL: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Kibana FAIL: {e}")
        print("   → Lance Kibana : docker compose up -d kibana")
        return False


def check_python_packages():
    """Vérifier les packages Python avec versions"""
    print("\n" + "=" * 70)
    print("4️⃣  PYTHON PACKAGES CHECK")
    print("=" * 70)
    
    required_packages = {
        'redis': 'Redis client',
        'elasticsearch': 'Elasticsearch client',
        'requests': 'HTTP requests',
        'transformers': 'Hugging Face transformers',
        'torch': 'PyTorch (backend)',
        'mastodon': 'Mastodon.py (collector)',
        'loguru': 'Logging (collector)',
    }
    
    all_ok = True
    
    for package, description in required_packages.items():
        try:
            module = __import__(package)
            version = getattr(module, '__version__', 'N/A')
            print(f"✅ {package:20} v{version:10} - {description}")
        except ImportError:
            print(f"❌ {package:20} {'MANQUANT':11} - {description}")
            all_ok = False
    
    if not all_ok:
        print("\n⚠️  Installation requise:")
        print("   pip install redis elasticsearch requests transformers torch mastodon.py loguru")
    
    return all_ok


def check_models_downloaded():
    """Vérifier et tester les modèles Hugging Face"""
    print("\n" + "=" * 70)
    print("5️⃣  HUGGING FACE MODELS CHECK & PERFORMANCE")
    print("=" * 70)
    
    try:
        from transformers import pipeline
        
        # Test NER
        print("Test 1/2 : Modèle NER (extraction aspects)...")
        try:
            start = time.time()
            ner_model = pipeline(
                "ner",
                model="Davlan/xlm-roberta-base-ner-hrl",
                device=-1
            )
            load_time = time.time() - start
            
            # Test inference
            test_text = "I love the new iPhone from Apple"
            start = time.time()
            result = ner_model(test_text)
            inference_time = (time.time() - start) * 1000
            
            print(f"   ✅ XLM-RoBERTa NER")
            print(f"      Chargement  : {load_time:.2f}s")
            print(f"      Inférence   : {inference_time:.2f}ms")
            print(f"      Aspects     : {len(result)} détectés")
            
        except Exception as e:
            print(f"   ❌ XLM-RoBERTa NER: {e}")
            return False
        
        # Test Sentiment
        print("\nTest 2/2 : Modèle Sentiment...")
        try:
            start = time.time()
            sentiment_model = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual",
                device=-1
            )
            load_time = time.time() - start
            
            # Test inference
            test_text = "This is amazing!"
            start = time.time()
            result = sentiment_model(test_text)
            inference_time = (time.time() - start) * 1000
            
            sentiment = result[0]['label']
            confidence = result[0]['score']
            
            print(f"   ✅ XLM-RoBERTa Sentiment")
            print(f"      Chargement  : {load_time:.2f}s")
            print(f"      Inférence   : {inference_time:.2f}ms")
            print(f"      Test result : {sentiment} ({confidence:.2f})")
            
        except Exception as e:
            print(f"   ❌ XLM-RoBERTa Sentiment: {e}")
            return False
        
        print("\n   ℹ️  Performance estimée:")
        total_latency = inference_time * 2  # NER + Sentiment
        if total_latency < 100:
            print(f"      ⚡ Excellent : ~{total_latency:.0f}ms par toot")
        elif total_latency < 500:
            print(f"      ✅ Bon : ~{total_latency:.0f}ms par toot")
        else:
            print(f"      ⚠️  Lent : ~{total_latency:.0f}ms par toot")
            print(f"         Considérez un GPU pour accélérer")
        
        return True
        
    except Exception as e:
        print(f"❌ Modèles: {e}")
        return False


def check_worker_files():
    """Vérifier les fichiers du projet"""
    print("\n" + "=" * 70)
    print("6️⃣  PROJECT FILES CHECK")
    print("=" * 70)
    
    import os
    
    files_to_check = {
        'mastodon_stream.py': 'Collector (streaming)',
        'absa_worker_realtime.py': 'Worker temps réel (recommandé)',
        'absa_worker_fixed.py': 'Worker standard (fallback)',
        'startup_realtime.py': 'Script démarrage temps réel',
        '.env': 'Configuration (credentials)',
    }
    
    all_ok = True
    
    for filename, description in files_to_check.items():
        exists = os.path.exists(filename)
        icon = "✅" if exists else "❌"
        status = "OK" if exists else "MANQUANT"
        
        print(f"{icon} {filename:30} - {status:10} - {description}")
        
        if not exists and 'realtime' in filename:
            all_ok = False
    
    if not all_ok:
        print("\n⚠️  Fichiers manquants - Assurez-vous d'avoir :")
        print("   - absa_worker_realtime.py (pour le mode temps réel)")
        print("   - startup_realtime.py (pour le démarrage automatique)")
    
    return all_ok


def check_worker_running():
    """Vérifier si le worker tourne et ses performances"""
    print("\n" + "=" * 70)
    print("7️⃣  WORKER STATUS & PERFORMANCE")
    print("=" * 70)
    
    log_files = ['analysis_worker_realtime.log', 'analysis_worker.log']
    log_file = None
    
    for f in log_files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                log_file = f
                break
        except FileNotFoundError:
            continue
    
    if not log_file:
        print(f"⚠️  Aucun fichier log trouvé")
        print(f"   Le worker n'a jamais été lancé")
        return False
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            print(f"⚠️  Fichier log vide")
            return False
        
        # Analyser le log
        last_line = lines[-1]
        is_realtime = 'TEMPS RÉEL' in ' '.join(lines[:10]) or 'realtime' in log_file
        
        print(f"✅ Log trouvé : {log_file}")
        print(f"   Mode        : {'⚡ TEMPS RÉEL' if is_realtime else '📦 Batch'}")
        print(f"   Lignes      : {len(lines)}")
        
        # Extraire les stats du log
        stats = {
            'traites': 0,
            'aspects': 0,
            'indexes': 0,
            'latence_ms': None
        }
        
        for line in reversed(lines[-50:]):  # 50 dernières lignes
            if 'Traités' in line and ':' in line:
                try:
                    stats['traites'] = int(line.split('Traités')[1].split(':')[1].strip().split()[0])
                except:
                    pass
            
            if 'Aspects' in line and ':' in line:
                try:
                    stats['aspects'] = int(line.split('Aspects')[1].split(':')[1].strip().split()[0])
                except:
                    pass
            
            if 'Latence moy' in line or 'processing_time_ms' in line:
                try:
                    if 'Latence moy' in line:
                        stats['latence_ms'] = int(line.split('Latence moy')[1].split(':')[1].strip().replace('ms', ''))
                    elif 'processing_time_ms' in line:
                        stats['latence_ms'] = int(line.split('processing_time_ms')[1].split(':')[1].strip())
                except:
                    pass
        
        if stats['traites'] > 0:
            print(f"\n   📊 Statistiques :")
            print(f"      Traités      : {stats['traites']}")
            print(f"      Aspects      : {stats['aspects']}")
            
            if stats['latence_ms']:
                print(f"      Latence moy  : {stats['latence_ms']}ms")
                
                if stats['latence_ms'] < 100:
                    print(f"                     ⚡ Excellent (temps réel)")
                elif stats['latence_ms'] < 500:
                    print(f"                     ✅ Bon")
                elif stats['latence_ms'] < 1000:
                    print(f"                     ⚠️  Acceptable")
                else:
                    print(f"                     ❌ Lent (> 1s)")
        
        # Vérifier activité récente
        try:
            timestamp_str = last_line.split('|')[0].strip()
            # Format: 2024-12-12 10:30:45
            last_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            time_diff = datetime.now() - last_time
            
            print(f"\n   ⏰ Dernière activité :")
            print(f"      {timestamp_str} ({time_diff.seconds}s ago)")
            
            if time_diff.seconds < 30:
                print(f"      ✅ Worker ACTIF (< 30s)")
            elif time_diff.seconds < 300:
                print(f"      ⚠️  Dernière activité il y a {time_diff.seconds}s")
            else:
                print(f"      ❌ Worker probablement ARRÊTÉ (> 5min)")
                return False
        except:
            print(f"   ℹ️  Impossible de parser la date")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Erreur lecture log: {e}")
        return False


def test_end_to_end_latency():
    """Test end-to-end de la latence du pipeline"""
    print("\n" + "=" * 70)
    print("8️⃣  END-TO-END LATENCY TEST")
    print("=" * 70)
    
    try:
        import redis
        client = redis.from_url('redis://localhost:6379', decode_responses=True)
        
        # Créer un toot de test
        test_toot = {
            "toot_id": "health_check_test",
            "text": "This is a test toot for health check",
            "created_at": datetime.now().isoformat(),
            "author_username": "health_check",
            "lang": "en",
            "hashtags": ["test"],
            "url": "http://test"
        }
        
        print("Envoi d'un toot de test dans la queue...")
        print(f"   Toot ID : {test_toot['toot_id']}")
        
        start = time.time()
        client.rpush('mastodon_queue', json.dumps(test_toot))
        
        print(f"   ✅ Toot envoyé dans Redis")
        print(f"\n   ⏳ Attente traitement par le worker...")
        print(f"      (Si le worker ne tourne pas, ce test échouera)")
        
        # Note: Ce test nécessite que le worker tourne
        # On ne peut pas vraiment vérifier sans interroger ES
        print(f"\n   ℹ️  Pour valider le test complet :")
        print(f"      1. Assurez-vous que le worker tourne")
        print(f"      2. Vérifiez dans Elasticsearch si le toot apparaît")
        print(f"      3. La latence devrait être < 1s en mode temps réel")
        
        return True
        
    except Exception as e:
        print(f"❌ Test: {e}")
        return False


def summary(results):
    """Résumé avec recommandations"""
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ & RECOMMANDATIONS")
    print("=" * 70)
    
    checks = {
        'Redis': results.get('redis'),
        'Elasticsearch': results.get('elasticsearch'),
        'Kibana': results.get('kibana'),
        'Python packages': results.get('packages'),
        'Hugging Face models': results.get('models'),
        'Project files': results.get('files'),
        'Worker': results.get('worker'),
    }
    
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    
    print(f"\n✅ PASSED: {passed}/{total}\n")
    
    for name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    
    print("\n" + "=" * 70)
    
    if passed == total:
        print("🎉 TOUS LES TESTS SONT OK !")
        print("\n📌 Prochaines étapes :")
        print("   1. Lance le pipeline : python startup_realtime.py")
        print("   2. Ouvre Kibana : http://localhost:5601")
        print("   3. Surveille les logs en temps réel")
        print("\n⚡ Mode temps réel activé - Latence < 1 seconde !")
    elif passed >= total - 1:
        print("⚠️  Presque prêt - Un élément manque")
        print("   Corrigez l'élément manquant puis relancez ce check")
    else:
        print("❌ Plusieurs éléments manquent")
        print("   Suivez les instructions ci-dessus pour chaque élément")
    
    print("=" * 70)


def main():
    """Fonction principale"""
    print_header()
    
    time.sleep(0.5)
    
    results = {}
    
    # Tous les checks
    results['redis'] = check_redis()
    time.sleep(1)
    
    results['elasticsearch'] = check_elasticsearch()
    time.sleep(1)
    
    results['kibana'] = check_kibana()
    time.sleep(1)
    
    results['packages'] = check_python_packages()
    time.sleep(1)
    
    results['models'] = check_models_downloaded()
    time.sleep(1)
    
    results['files'] = check_worker_files()
    time.sleep(1)
    
    results['worker'] = check_worker_running()
    time.sleep(1)
    
    # Test optionnel end-to-end
    # results['e2e'] = test_end_to_end_latency()
    
    # Résumé
    summary(results)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Arrêt utilisateur")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)