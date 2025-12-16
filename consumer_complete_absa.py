"""
CONSUMER COMPLET ABSA - TEMPS RÉEL + ELASTICSEARCH
Optimisations pour latence minimale (<500ms):
- Modèles légers et pré-chargés
- Traitement parallèle avec asyncio
- Indexation Elasticsearch temps réel
- Batch indexing pour perfo
- Caching des résultats
"""

import redis
import json
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict, deque
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

# Fix encoding Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ================================================
# CONFIGURATION TEMPS RÉEL + ELASTICSEARCH
# ================================================
REDIS_URL = 'redis://localhost:6379'
ELASTICSEARCH_URL = 'http://localhost:9200'  # URL Elasticsearch
QUEUE_NAME = 'mastodon_queue'
SAVE_RESULTS = True
OUTPUT_FILE = 'absa_results.jsonl'

# Optimisations temps réel
WORKERS = 6
BATCH_SIZE = 15
CACHE_SIZE = 2000
USE_GPU = False
LIGHT_MODELS = True

# Elasticsearch indexing
ES_INDEX_NAME = 'absa-analysis'  # Nom de l'index
BATCH_INDEX_SIZE = 20  # Indexer par batch de 20
BULK_REFRESH_INTERVAL = 2  # Seconds

# ================================================
# CACHE LRU SIMPLE
# ================================================
class LRUCache:
    def __init__(self, max_size=1000):
        self.cache = {}
        self.access_order = deque()
        self.max_size = max_size
    
    def get(self, key):
        if key in self.cache:
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None
    
    def put(self, key, value):
        if key in self.cache:
            self.access_order.remove(key)
        elif len(self.cache) >= self.max_size:
            oldest = self.access_order.popleft()
            del self.cache[oldest]
        
        self.cache[key] = value
        self.access_order.append(key)
    
    def clear(self):
        self.cache.clear()
        self.access_order.clear()


# ================================================
# ELASTICSEARCH MANAGER
# ================================================
class ElasticsearchManager:
    def __init__(self, es_url=ELASTICSEARCH_URL, index_name=ES_INDEX_NAME):
        """Initialiser la connexion Elasticsearch"""
        self.es = Elasticsearch([es_url])
        self.index_name = index_name
        self.bulk_buffer = []
        self.last_bulk_time = time.time()
        
        print("=" * 70)
        print("INITIALISATION ELASTICSEARCH")
        print("=" * 70)
        
        try:
            # Test de connexion
            info = self.es.info()
            print(f"✓ Connexion Elasticsearch OK")
            print(f"  Version: {info['version']['number']}")
        except Exception as e:
            print(f"✗ Erreur Elasticsearch: {e}")
            print("  → Lance: docker run -d -p 9200:9200 docker.elastic.co/elasticsearch/elasticsearch:8.0.0")
            sys.exit(1)
        
        # Créer l'index s'il n'existe pas
        self._create_index()
        print(f"✓ Index '{self.index_name}' prêt\n")
    
    def _create_index(self):
        """Créer l'index avec mapping optimal"""
        if self.es.indices.exists(index=self.index_name):
            return
        
        mapping = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "1s"  # Refresh rapide pour temps réel
            },
            "mappings": {
                "properties": {
                    # Identifiants
                    "toot_id": {"type": "keyword"},
                    "author": {"type": "keyword"},
                    "instance": {"type": "keyword"},
                    
                    # Texte
                    "text": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {
                            "raw": {"type": "keyword"}
                        }
                    },
                    "language": {"type": "keyword"},
                    
                    # Aspects (nested pour recherche avancée)
                    "aspects": {
                        "type": "nested",
                        "properties": {
                            "aspect": {"type": "keyword"},
                            "polarity": {"type": "keyword"},
                            "confidence": {"type": "float"}
                        }
                    },
                    
                    # Sentiment global
                    "overall_sentiment": {
                        "type": "object",
                        "properties": {
                            "polarity": {"type": "keyword"},
                            "score": {"type": "float"}
                        }
                    },
                    
                    # Émotions (nested)
                    "emotions": {
                        "type": "nested",
                        "properties": {
                            "emotion": {"type": "keyword"},
                            "score": {"type": "float"}
                        }
                    },
                    
                    # Topic
                    "topic": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "keyword"},
                            "confidence": {"type": "float"}
                        }
                    },
                    
                    # Métadata
                    "created_at": {"type": "date"},
                    "latency_ms": {"type": "float"},
                    "hashtags": {"type": "keyword"},
                    "timestamp": {"type": "date"}
                }
            }
        }
        
        self.es.indices.create(index=self.index_name, body=mapping)
    
    def index_analysis(self, analysis: Dict):
        """Ajouter une analyse au buffer bulk"""
        doc = {
            "_index": self.index_name,
            "_id": analysis['toot_id'],
            "_source": {
                **analysis,
                "timestamp": datetime.now().isoformat()
            }
        }
        self.bulk_buffer.append(doc)
        
        # Indexer si buffer plein ou timeout écoulé
        if (len(self.bulk_buffer) >= BATCH_INDEX_SIZE or 
            time.time() - self.last_bulk_time > BULK_REFRESH_INTERVAL):
            self.flush_bulk()
    
    def flush_bulk(self):
        """Indexer tous les documents du buffer"""
        if not self.bulk_buffer:
            return
        
        try:
            # Bulk index
            success, errors = bulk(self.es, self.bulk_buffer, raise_on_error=False)
            
            if errors:
                print(f"⚠ Erreurs Elasticsearch: {len(errors)} docs")
            else:
                print(f"✓ Indexed {success} documents")
            
            self.bulk_buffer = []
            self.last_bulk_time = time.time()
            
        except Exception as e:
            print(f"✗ Erreur bulk indexing: {e}")
    
    def search_by_aspect(self, aspect: str, polarity: str = None, limit: int = 10):
        """Rechercher par aspect et polarity optionnelle"""
        query = {
            "query": {
                "nested": {
                    "path": "aspects",
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"aspects.aspect": aspect}}
                            ]
                        }
                    }
                }
            },
            "size": limit,
            "sort": [{"created_at": {"order": "desc"}}]
        }
        
        if polarity:
            query["query"]["nested"]["query"]["bool"]["must"].append(
                {"term": {"aspects.polarity": polarity}}
            )
        
        return self.es.search(index=self.index_name, body=query)
    
    def search_by_emotion(self, emotion: str, min_score: float = 0.5, limit: int = 10):
        """Rechercher par émotion"""
        query = {
            "query": {
                "nested": {
                    "path": "emotions",
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"emotions.emotion": emotion}},
                                {"range": {"emotions.score": {"gte": min_score}}}
                            ]
                        }
                    }
                }
            },
            "size": limit,
            "sort": [{"created_at": {"order": "desc"}}]
        }
        
        return self.es.search(index=self.index_name, body=query)
    
    def search_by_topic(self, topic: str, limit: int = 10):
        """Rechercher par topic"""
        query = {
            "query": {
                "term": {"topic.topic": topic}
            },
            "size": limit,
            "sort": [{"created_at": {"order": "desc"}}]
        }
        
        return self.es.search(index=self.index_name, body=query)
    
    def stats(self):
        """Obtenir les stats de l'index"""
        return self.es.indices.stats(index=self.index_name)


# ================================================
# ANALYSEUR ABSA TEMPS RÉEL
# ================================================
class RealtimeABSAAnalyzer:
    def __init__(self, es_manager: ElasticsearchManager):
        print("=" * 70)
        print("ANALYSEUR ABSA TEMPS RÉEL + ELASTICSEARCH")
        print("=" * 70)
        
        self.es_manager = es_manager
        self.nlp_models = {}
        self.sentiment_model = None
        self.emotion_model = None
        self.zero_shot_model = None
        
        # Caching
        self.aspect_cache = LRUCache(CACHE_SIZE)
        self.sentiment_cache = LRUCache(CACHE_SIZE)
        
        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=WORKERS)
        
        # Stats
        self.stats = {
            'total_processed': 0,
            'total_analyzed': 0,
            'cache_hits': 0,
            'es_indexed': 0,
            'avg_latency': 0.0,
            'latencies': deque(maxlen=100),
            'start_time': datetime.now(),
            'by_language': defaultdict(int),
            'by_emotion': defaultdict(int),
        }
        
        # Stopwords
        self.stopwords = {
            'être', 'avoir', 'faire', 'the', 'a', 'an', 'and', 'or',
            'de', 'le', 'la', 'les', 'un', 'une', 'des', 'is', 'are'
        }
        
        # Topics
        self.topic_labels = [
            "tech & AI", "politics", "business", "environment",
            "entertainment", "health", "education", "sports"
        ]
        
        # Patterns
        self.url_pattern = re.compile(r'https?://[^\s]+|www\.[^\s]+|t\.co/[^\s]+')
        self.mention_pattern = re.compile(r'@[\w]+')
        
        # Output
        self.output_file = None
        if SAVE_RESULTS:
            self.output_file = open(OUTPUT_FILE, 'a', encoding='utf-8')
        
        print("\n⚡ Chargement modèles légers...")
        self._init_models()
        print("✓ Analyseur initialisé\n")
    
    def _init_models(self):
        """Charger modèles optimisés"""
        try:
            # spaCy
            try:
                import spacy
                self.nlp_models['en'] = spacy.load('en_core_web_sm')
                print("  ✓ spaCy EN (lightweight)")
            except:
                print("  ⚠ spaCy EN unavailable")
            
            # Transformers - Modèles légers
            try:
                from transformers import pipeline
                
                device = 0 if USE_GPU else -1
                
                print("  Chargement sentiment (Twitter XLM-RoBERTa)...")
                self.sentiment_model = pipeline(
                    "sentiment-analysis",
                    model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
                    device=device,
                    truncation=True,
                    max_length=256
                )
                print("  ✓ Sentiment model (Twitter XLM-RoBERTa)")
                
                print("  Chargement émotions...")
                self.emotion_model = pipeline(
                    "text-classification",
                    model="bhadresh-savani/distilbert-base-uncased-emotion",
                    device=device,
                    top_k=None,
                    truncation=True,
                    max_length=256
                )
                print("  ✓ Emotion model (DistilBERT)")
                
                print("  Chargement topic detection...")
                self.zero_shot_model = pipeline(
                    "zero-shot-classification",
                    model="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
                    device=device
                )
                print("  ✓ Topic model (léger)")
                
            except Exception as e:
                print(f"  ⚠ Transformers error: {e}")
        
        except ImportError as e:
            print(f"  ⚠ Missing deps: {e}")
    
    def extract_aspects_fast(self, text: str, lang: str = 'en') -> List[str]:
        """Extraction aspects ultra-rapide"""
        cache_key = f"aspects:{hash(text)}"
        cached = self.aspect_cache.get(cache_key)
        if cached:
            self.stats['cache_hits'] += 1
            return cached
        
        aspects = set()
        nlp = self.nlp_models.get(lang) or self.nlp_models.get('en')
        
        if nlp:
            try:
                doc = nlp(text)
                for token in doc:
                    if token.pos_ in {"NOUN", "PROPN", "ADJ"}:
                        aspect = token.lemma_.lower().strip()
                        
                        if (2 <= len(aspect) <= 30 and 
                            aspect not in self.stopwords and
                            not self.url_pattern.match(aspect) and
                            not self.mention_pattern.match(aspect)):
                            aspects.add(aspect)
                
                result = list(aspects)[:8]
                self.aspect_cache.put(cache_key, result)
                return result
            except:
                pass
        
        words = text.lower().split()[:50]
        for word in words:
            word = word.strip('.,!?;:()')
            if 3 <= len(word) <= 30 and word not in self.stopwords:
                aspects.add(word)
        
        result = list(aspects)[:8]
        self.aspect_cache.put(cache_key, result)
        return result
    
    def analyze_sentiment_fast(self, text: str, aspect: str) -> Dict:
        """Analyse sentiment ultra-rapide avec cache"""
        if not self.sentiment_model:
            return {"polarity": "neutral", "score": 0.5}
        
        cache_key = f"sent:{aspect}:{hash(text[:256])}"
        cached = self.sentiment_cache.get(cache_key)
        if cached:
            self.stats['cache_hits'] += 1
            return cached
        
        try:
            sentences = text.split('.')
            aspect_sentences = [s for s in sentences if aspect in s.lower()][:1]
            
            context = (aspect_sentences[0] if aspect_sentences else text)[:256]
            result = self.sentiment_model(context)[0]
            
            label = result['label'].lower()
            polarity = 'positive' if label in ['positive', 'pos'] else \
                      'negative' if label in ['negative', 'neg'] else 'neutral'
            
            response = {
                "polarity": polarity,
                "score": round(result['score'], 3)
            }
            
            self.sentiment_cache.put(cache_key, response)
            return response
        except Exception as e:
            return {"polarity": "neutral", "score": 0.5}
    
    def detect_emotions_fast(self, text: str) -> List[Dict]:
        """Émotions ultra-rapides"""
        if not self.emotion_model:
            return []
        
        try:
            results = self.emotion_model(text[:256])
            emotions = []
            
            for result in results[0]:
                if result['score'] > 0.2:
                    emotions.append({
                        "emotion": result['label'],
                        "score": round(result['score'], 3)
                    })
                    self.stats['by_emotion'][result['label']] += 1
            
            emotions.sort(key=lambda x: x['score'], reverse=True)
            return emotions[:3]
        except:
            return []
    
    def detect_topic_fast(self, text: str) -> Dict:
        """Détection topic rapide"""
        if not self.zero_shot_model:
            return {"topic": "unknown", "confidence": 0.0}
        
        try:
            short_labels = self.topic_labels[:4]
            result = self.zero_shot_model(
                text[:200],
                candidate_labels=short_labels,
                multi_label=False
            )
            
            return {
                "topic": result['labels'][0],
                "confidence": round(result['scores'][0], 3)
            }
        except:
            return {"topic": "unknown", "confidence": 0.0}
    
    async def analyze_toot_async(self, toot: Dict) -> Optional[Dict]:
        """Analyse async - indexation Elasticsearch"""
        text = toot.get('text', '').strip()
        lang = toot.get('lang', 'en')
        
        if not text or len(text) < 5:
            return None
        
        start_time = time.time()
        self.stats['total_processed'] += 1
        self.stats['by_language'][lang] += 1
        
        try:
            loop = asyncio.get_event_loop()
            
            # Extraction aspects
            aspects = self.extract_aspects_fast(text, lang)
            if not aspects:
                return None
            
            # Sentiments par aspect (parallèle)
            aspect_sentiments = []
            tasks = []
            for aspect in aspects[:6]:
                task = loop.run_in_executor(
                    self.executor,
                    self.analyze_sentiment_fast,
                    text,
                    aspect
                )
                tasks.append((aspect, task))
            
            for aspect, task in tasks:
                sentiment = await task
                aspect_sentiments.append({
                    "aspect": aspect,
                    "polarity": sentiment['polarity'],
                    "confidence": sentiment.get('score', 0.0)
                })
            
            # Émotions
            emotions_task = loop.run_in_executor(
                self.executor,
                self.detect_emotions_fast,
                text
            )
            emotions = await emotions_task
            
            # Topic
            topic_task = loop.run_in_executor(
                self.executor,
                self.detect_topic_fast,
                text
            )
            topic = await topic_task
            
            # Sentiment global
            overall_task = loop.run_in_executor(
                self.executor,
                self.analyze_sentiment_fast,
                text,
                "overall"
            )
            overall_sentiment = await overall_task
            
            # Construire résultat
            analysis = {
                "toot_id": toot.get('toot_id'),
                "created_at": toot.get('created_at'),
                "language": lang,
                "text": text[:150],
                "instance": toot.get('instance'),
                "author": toot.get('author_username'),
                "aspects": aspect_sentiments,
                "overall_sentiment": overall_sentiment,
                "emotions": emotions,
                "topic": topic,
                "hashtags": toot.get('hashtags', []),
                "latency_ms": round((time.time() - start_time) * 1000, 1)
            }
            
            self.stats['total_analyzed'] += 1
            self.stats['latencies'].append(analysis['latency_ms'])
            self.stats['avg_latency'] = sum(self.stats['latencies']) / len(self.stats['latencies'])
            
            # ✨ INDEXER DANS ELASTICSEARCH ✨
            self.es_manager.index_analysis(analysis)
            self.stats['es_indexed'] += 1
            
            # Sauvegarder local
            if self.output_file:
                self.output_file.write(json.dumps(analysis, ensure_ascii=False) + '\n')
                self.output_file.flush()
            
            return analysis
            
        except Exception as e:
            print(f"✗ Error: {e}")
            return None
    
    def print_analysis_compact(self, analysis: Dict, count: int):
        """Affichage ultra-compact"""
        print(f"\n[#{count:04d}] ⚡ {analysis['latency_ms']:.0f}ms | {analysis['language'].upper()} | {analysis['text'][:60]}...")
        
        aspects_str = " | ".join([f"{a['aspect']}({a['polarity'][0]})" 
                                  for a in analysis['aspects'][:3]])
        print(f"  📊 {aspects_str}")
        
        if analysis['emotions']:
            emo_str = " ".join([f"{e['emotion']}({e['score']:.0%})" 
                               for e in analysis['emotions'][:2]])
            print(f"  😊 {emo_str}")
        
        print(f"  🎯 {analysis['topic']['topic']} | Sent: {analysis['overall_sentiment']['polarity']}")
        print(f"  🔍 Indexed in Elasticsearch ✓")
    
    def print_stats_realtime(self):
        """Stats temps réel"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        
        print("\n" + "=" * 70)
        print(f"⚡ STATS TEMPS RÉEL - {elapsed:.0f}s")
        print("=" * 70)
        print(f"Traités:    {self.stats['total_processed']:4d} | "
              f"Analysés:    {self.stats['total_analyzed']:4d} | "
              f"Cache hits: {self.stats['cache_hits']:4d}")
        print(f"Latence:    {self.stats['avg_latency']:.1f}ms avg | "
              f"Débit:      {self.stats['total_analyzed']/elapsed:.1f} toot/s")
        print(f"Elasticsearch: {self.stats['es_indexed']} docs indexés")
        print("=" * 70 + "\n")
    
    def close(self):
        if self.output_file:
            self.output_file.close()
        self.executor.shutdown(wait=False)
        self.es_manager.flush_bulk()  # Indexer les derniers docs


# ================================================
# CONSUMER ASYNC TEMPS RÉEL
# ================================================
async def consumer_realtime(analyzer, es_manager):
    """Consumer async pour latence minimale"""
    try:
        redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5
        )
        redis_client.ping()
        print("✓ Redis OK\n")
    except:
        print("✗ Redis unavailable")
        return
    
    print("=" * 70)
    print("ANALYSE TEMPS RÉEL + ELASTICSEARCH EN COURS (Ctrl+C pour arrêter)")
    print("=" * 70 + "\n")
    
    count = 0
    last_stats = time.time()
    batch = []
    
    try:
        while True:
            # Consommer sans bloquer
            result = redis_client.blpop(QUEUE_NAME, timeout=0.5)
            
            if result:
                _, toot_json = result
                try:
                    toot = json.loads(toot_json)
                    batch.append(toot)
                    
                    # Traiter par batch
                    if len(batch) >= BATCH_SIZE:
                        tasks = [analyzer.analyze_toot_async(t) for t in batch]
                        results = await asyncio.gather(*tasks)
                        
                        for analysis in results:
                            if analysis:
                                count += 1
                                analyzer.print_analysis_compact(analysis, count)
                        
                        batch = []
                
                except json.JSONDecodeError:
                    pass
            
            # Stats
            if time.time() - last_stats > 30:
                analyzer.print_stats_realtime()
                last_stats = time.time()
            
            await asyncio.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\n\n✓ Arrêt demandé")
    finally:
        analyzer.print_stats_realtime()
        analyzer.close()
        print(f"✓ {analyzer.stats['es_indexed']} documents indexés dans Elasticsearch")


# ================================================
# MAIN
# ================================================
async def main():
    # Initialiser Elasticsearch
    es_manager = ElasticsearchManager()
    
    # Initialiser Analyzer
    analyzer = RealtimeABSAAnalyzer(es_manager)
    
    # Lancer consumer
    await consumer_realtime(analyzer, es_manager)


if __name__ == "__main__":
    asyncio.run(main())