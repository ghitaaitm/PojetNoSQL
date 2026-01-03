


import os, sys, re, json, time, signal, logging, random
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import redis

# Windows stdout encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler('worker_absa_v2_extended.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("worker-absa")

# Config (env-friendly)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
QUEUE_NAME = os.getenv('REDIS_QUEUE_NAME', os.getenv('QUEUE_NAME', 'mastodon_queue'))
ES_HOST = os.getenv('ES_HOST', 'http://localhost:9200')
ES_INDEX_PREFIX = os.getenv('ES_INDEX_PREFIX', 'mastodon-trends')
FILTER_MODE = os.getenv('FILTER_MODE', 'permissive').lower()
BLPOP_TIMEOUT = int(os.getenv('BLPOP_TIMEOUT', '1'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_BASE_SLEEP = float(os.getenv('RETRY_BASE_SLEEP', '0.6'))

FILTER_CONFIGS = {
    'strict': {
        'min_aspect_length': 3,
        'max_repetitions': 6,
        'allowed_pos': {"NOUN", "PROPN", "ADJ"},
        'use_extended_stopwords': True
    },
    'balanced': {
        'min_aspect_length': 2,
        'max_repetitions': 10,
        'allowed_pos': {"NOUN", "PROPN", "ADJ", "VERB"},
        'use_extended_stopwords': False
    },
    'permissive': {
        'min_aspect_length': 2,
        'max_repetitions': 15,
        'allowed_pos': {"NOUN", "PROPN", "ADJ", "VERB", "ADV"},
        'use_extended_stopwords': False
    },
}
CFG = FILTER_CONFIGS.get(FILTER_MODE, FILTER_CONFIGS['balanced'])


def jitter_sleep(base: float, attempt: int):
    time.sleep(base * (1.0 + 0.3 * random.random()) * attempt)


class CriticalToneDetector:
    def __init__(self):
        self.metaphors = {
            'surveillance capitalism': 'critique_privacy',
            'gig economy': 'critique_precarity'
        }
        self.words = {
            'exploitation', 'precarious', 'inequality', 'unfair',
            'exploité', 'précaire', 'inégalité', 'injustice'
        }
        self.emojis = {'🙄', '😒', '😤', '😠', '😡', '🚩', '⚠️', '❌'}

    def analyze(self, text: str) -> Dict:
        t = text.lower()
        score = 0.0
        sig = []

        for m in self.metaphors:
            if m in t:
                score += 0.4
                sig.append(f"metaphor:{m}")
                break

        k = sum(1 for w in self.words if w in t)
        if k:
            score += min(0.5, 0.15 * k)
            sig.append(f"keywords:{k}")

        e = sum(text.count(x) for x in self.emojis)
        if e:
            score += min(0.3, 0.1 * e)
            sig.append(f"emoji:{e}")

        if score >= 0.65:
            tone = 'critical'
        elif score >= 0.45:
            tone = 'skeptical'
        elif score >= 0.25:
            tone = 'questioning'
        else:
            tone = 'neutral'

        return {'tone': tone, 'critical_score': round(score, 3), 'signals': sig}


class ABSAWorker:
    def __init__(self):
        log.info("=" * 80)
        log.info("WORKER ABSA V2 (Extended) - Corrigé Final")
        log.info("=" * 80)

        self.redis = self._init_redis()
        self.es = self._init_es()
        self.nlp = {}
        self.sentiment = None
        self.emotion = None
        self.tone = CriticalToneDetector()
        self.stop = False

        # Stopwords
        self.stopwords = {'être', 'avoir', 'faire', 'the', 'a', 'an', 'and', 'or'}
        if CFG['use_extended_stopwords']:
            self.stopwords |= {'dire', 'aller', 'pouvoir', 'but', 'in', 'on', 'at'}

        self.url_rx = re.compile(r'https?://[^\s]+|www\.[^\s]+|t\.co/[^\s]+', re.I)
        self.mention_rx = re.compile(r'@[\w]+')

        # Stats
        self.stats = defaultdict(int)
        self.start = datetime.now(timezone.utc)

        # Ensure template + month index exist
        self._ensure_index_template()
        self._ensure_month_index()

        # Detect emotions mapping (informational)
        self.emotions_mode = self._detect_emotions_mode()
        log.info(f"🔎 Emotions mapping mode detected: {self.emotions_mode}")

    def _init_redis(self):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = redis.from_url(REDIS_URL, decode_responses=True,
                                   socket_connect_timeout=5, retry_on_timeout=True)
                r.ping()
                size = r.llen(QUEUE_NAME)
                log.info(f"✅ Redis OK | queue={QUEUE_NAME} | size={size}")
                return r
            except Exception as e:
                log.error(f"Redis init failed: {e} (attempt {attempt}/{MAX_RETRIES})")
                jitter_sleep(RETRY_BASE_SLEEP, attempt)
        raise RuntimeError("Redis init failed")

    def _init_es(self):
        try:
            from elasticsearch import Elasticsearch
            es = Elasticsearch(
                [ES_HOST],
                request_timeout=15,
                max_retries=2,
                retry_on_timeout=True,
                verify_certs=False,
                ssl_show_warn=False
            )
            info = es.info()
            log.info(f"✅ ES OK v{info['version']['number']}")
            return es
        except Exception as e:
            log.error(f"Elasticsearch init failed: {e}")
            return None

    def _index_name(self):
        return f"{ES_INDEX_PREFIX}-{datetime.now(timezone.utc):%Y-%m}"

    def _ensure_index_template(self):
        if not self.es:
            return

        tpl_name = f"{ES_INDEX_PREFIX}-tpl"
        body = {
            "index_patterns": [f"{ES_INDEX_PREFIX}-*"],
            "template": {
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
                        "text": {"type": "text"},
                        "aspects": {"type": "keyword"},
                        "sentiment": {
                            "properties": {
                                "label": {"type": "keyword"},
                                "score": {"type": "float"}
                            }
                        },
                        "emotions": {"type": "object"}, # ou "nested" si tu veux des agrégations plus fines,  # source field (flexible)
                        "emotions_flat": {"type": "keyword"},  # ALWAYS present for Kibana
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
        }

        try:
            self.es.indices.put_index_template(name=tpl_name, body=body)
            log.info("✓ Index template ensured")
        except Exception as e:
            log.warning(f"Index template warning: {e}")

    def _ensure_month_index(self):
        if not self.es:
            return

        idx = self._index_name()
        try:
            if not self.es.indices.exists(index=idx):
                self.es.indices.create(index=idx)
                log.info(f"✓ Month index created: {idx}")
            else:
                # Ensure emotions_flat mapping present
                self.es.indices.put_mapping(
                    index=idx,
                    body={"properties": {"emotions_flat": {"type": "keyword"}}}
                )
                log.info(f"✓ Mapping verified: emotions_flat keyword in {idx}")
        except Exception as e:
            log.error(f"Month index ensure failed: {e}")

    def _detect_emotions_mode(self):
        if not self.es:
            return "keyword"

        idx = self._index_name()
        try:
            m = self.es.indices.get_mapping(index=idx)
            prop = m.get(idx, {}).get('mappings', {}).get('properties', {}).get('emotions', {})
            t = prop.get('type')
            return 'nested' if t in ('nested', 'object') else 'keyword'
        except Exception:
            return 'keyword'

    def _init_spacy(self, lang='fr'):
        try:
            import spacy
            name = {
                'fr': 'fr_core_news_sm',
                'en': 'en_core_web_sm',
                'es': 'es_core_news_sm',
                'de': 'de_core_news_sm'
            }.get(lang, 'en_core_web_sm')

            try:
                nlp = spacy.load(name)
            except OSError:
                log.warning(f"spaCy model {name} not found; fallback EN")
                nlp = spacy.load("en_core_web_sm")
                lang = 'en'

            self.nlp[lang] = nlp
            return nlp
        except Exception as e:
            log.error(f"spaCy init error: {e}")
            return None

    def _init_sentiment(self):
        if self.sentiment:
            return self.sentiment

        try:
            from transformers import pipeline
            self.sentiment = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual",
                device=-1,
                truncation=True,
                max_length=512
            )
            log.info("✓ Sentiment model ready")
            return self.sentiment
        except Exception as e:
            log.error(f"Sentiment init error: {e}")
            return None

    def _init_emotion(self):
        if self.emotion:
            return self.emotion

        try:
            from transformers import pipeline
            self.emotion = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                device=-1,
                truncation=True,
                max_length=512,
                top_k=None
            )
            log.info("✓ Emotion model ready")
            return self.emotion
        except Exception as e:
            log.error(f"Emotion init error: {e}")
            return None

    def _flatten_emotions(self, emotions):
        """
        Convertit emotions (nested ou keyword) en liste de strings.
        - Si emotions = ["joy", "anger"] → retourne telle quelle
        - Si emotions = [{"emotion":"joy","score":0.9},...] → extrait ["joy",...]
        """
        if not emotions:
            return []

        if isinstance(emotions, list) and all(isinstance(e, str) for e in emotions):
            return emotions

        if isinstance(emotions, list) and all(isinstance(e, dict) and 'emotion' in e for e in emotions):
            return [e['emotion'] for e in emotions if e.get('emotion')]

        return []

    def analyze_emotions(self, text: str):
        if not self._init_emotion():
            return []

        try:
            results = self.emotion(text[:512], top_k=None)
            rows = results[0] if isinstance(results, list) and isinstance(results[0], list) else results

            if not isinstance(rows, list):
                return []

            pairs = []
            for it in rows:
                lbl = it.get('label')
                sc = it.get('score')
                try:
                    sc = float(sc)
                    if lbl and sc > 0.1:
                        pairs.append((lbl, sc))
                except (TypeError, ValueError):
                    pass

            pairs.sort(key=lambda x: x[1], reverse=True)

            # Source field emotions: on garde le format original (nested ou keyword)
            if self.emotions_mode == 'nested':
                return [{'emotion': l, 'score': round(s, 3)} for l, s in pairs[:5]]
            return [l for l, _ in pairs[:3]]

        except Exception as e:
            self.stats['emotion_errors'] += 1
            if self.stats['emotion_errors'] % 8 == 1:
                log.error(f"Emotion error: {e}")
            return []

    def is_valid_aspect(self, token, text: str) -> Tuple[bool, Optional[str]]:
        if not token or not token.text.strip():
            return False, 'empty'

        a = token.text.strip().lower()

        if len(a) < CFG['min_aspect_length']:
            return False, 'too_short'

        if self.url_rx.match(a) or self.mention_rx.match(a):
            return False, 'url_or_mention'

        if a in self.stopwords:
            return False, 'stopword'

        if token.pos_ not in CFG['allowed_pos']:
            return False, 'wrong_pos'

        if not re.search(r'[a-zA-ZÀ-ÿ]', a):
            return False, 'no_alpha'

        if text.lower().count(a) > CFG['max_repetitions']:
            return False, 'too_repetitive'

        return True, None

    def extract_aspects(self, text: str, lang: str) -> List[str]:
        nlp = self._init_spacy(lang or 'fr')
        if not nlp:
            return []

        try:
            aspects = set()
            doc = nlp(text)
            for tok in doc:
                ok, reason = self.is_valid_aspect(tok, text)
                if ok:
                    aspects.add(tok.lemma_.lower())
                    self.stats['aspects_found'] += 1
                else:
                    self.stats['aspects_filtered'] += 1
                    if reason:
                        self.stats[f'filter_{reason}'] += 1

            return list(aspects)
        except Exception as e:
            log.error(f"Aspect extraction error: {e}")
            return []

    def analyze_sentiment(self, text: str, tone: Dict) -> Dict:
        m = self._init_sentiment()
        if not m:
            return {"label": "neutral", "score": 0.0}

        try:
            out = m(text[:512])[0]
            label = out["label"].lower()
            score = float(out["score"])

            if tone.get("critical_score", 0.0) >= 0.7 and label in ("positive", "pos"):
                label = "critical_ironic"

            return {"label": label, "score": round(score, 3)}
        except Exception as e:
            log.error(f"Sentiment error: {e}")
            return {"label": "neutral", "score": 0.0}

    def analyze_absa(self, toot: Dict) -> Optional[Dict]:
        text = (toot.get("text") or "").strip()
        if not text:
            return None

        lang = (toot.get("lang") or "fr").lower()
        tone = self.tone.analyze(text)

        if tone["tone"] == "critical":
            self.stats['critical_tone'] += 1
        elif tone["tone"] == "skeptical":
            self.stats['skeptical_tone'] += 1

        aspects = self.extract_aspects(text, lang)
        if not aspects:
            return None

        sentiment = self.analyze_sentiment(text, tone)
        emotions = self.analyze_emotions(text)
        emotions_flat = self._flatten_emotions(emotions)  # CORRECTION CLÉ

        doc = {
            "id": toot.get("toot_id"),
            "created_at": toot.get("created_at"),
            "language": lang,
            "text": text[:500],
            "aspects": aspects,
            "sentiment": sentiment,
            "emotions": emotions,  # source field (nested ou keyword)
            "emotions_flat": emotions_flat,  # TOUJOURS keyword list (Kibana-friendly)
            "critical_tone": tone,
            "metadata": {
                "hashtags": toot.get("hashtags", []),
                "author": toot.get("author_username", ""),
                "instance": toot.get("instance", "")
            }
        }

        return doc

    def index_doc(self, idx: str, doc_id: str, doc: Dict):
        if not self.es:
            return False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self.es.index(index=idx, id=doc_id, document=doc)
                return True
            except Exception as e:
                log.error(f"Index attempt {attempt} failed: {e}")
                jitter_sleep(RETRY_BASE_SLEEP, attempt)

        return False

    def process_toot(self, toot_json: str):
        try:
            toot = json.loads(toot_json)
            doc = self.analyze_absa(toot)

            if doc:
                idx = self._index_name()
                doc_id = toot.get("toot_id") or str(hash(toot_json))
                ok = self.index_doc(idx, doc_id, doc)
                self.stats['indexed'] += int(ok)
                self.stats['processed'] += 1

        except Exception as e:
            self.stats['errors'] += 1
            log.error(f"Process error: {e}")

    def log_stats(self):
        uptime = (datetime.now(timezone.utc) - self.start).total_seconds()
        kept = self.stats['aspects_found']
        filt = self.stats['aspects_filtered']
        total = kept + filt
        pct = (kept / total * 100.0) if total else 0.0

        log.info("=" * 70)
        log.info(f"📊 STATS [{FILTER_MODE.upper()}] {uptime:.0f}s | emotions:{self.emotions_mode} | indexed:{self.stats['indexed']}")
        log.info(f"🔍 aspects kept:{kept} filtered:{filt} ({pct:.1f}%) | critical:{self.stats['critical_tone']} skeptical:{self.stats['skeptical_tone']}")
        log.info(f"😊 emotions errors:{self.stats['emotion_errors']}")
        log.info("=" * 70)

    def backfill_emotions_flat(self, months: List[str]):
        """
        Optional: populate emotions_flat for existing monthly indices.
        months format: ['2025-10','2025-11','2025-12']
        """
        if not self.es:
            return

        for m in months:
            idx = f"{ES_INDEX_PREFIX}-{m}"
            try:
                # Ensure mapping
                self.es.indices.put_mapping(
                    index=idx,
                    body={"properties": {"emotions_flat": {"type": "keyword"}}}
                )

                # Painless script to flatten source field
                script = """
                if (ctx._source.emotions != null) {
                    def out = [];
                    if (ctx._source.emotions instanceof List) {
                        for (def e in ctx._source.emotions) {
                            if (e instanceof Map && e.containsKey('emotion')) {
                                out.add(e.get('emotion'));
                            } else if (e instanceof String) {
                                out.add(e);
                            }
                        }
                    }
                    ctx._source.emotions_flat = out;
                }
                """

                body = {
                    "script": {"source": script, "lang": "painless"},
                    "query": {"bool": {"must": [{"exists": {"field": "emotions"}}]}}
                }

                resp = self.es.update_by_query(index=idx, body=body, refresh=True, conflicts="proceed")
                log.info(f"✓ Backfill emotions_flat on {idx}: updated={resp.get('updated')}")

            except Exception as e:
                log.error(f"Backfill failed on {idx}: {e}")

    def run(self):
        log.info(f"🚀 Worker running | queue={QUEUE_NAME} | mode={FILTER_MODE}")
        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)

        c = 0
        while not self.stop:
            try:
                item = self.redis.blpop(QUEUE_NAME, timeout=BLPOP_TIMEOUT)
                if item:
                    _, j = item
                    self.process_toot(j)
                    c += 1
                    if c % 20 == 0:
                        self.log_stats()
                        c = 0

            except Exception as e:
                log.error(f"Loop error: {e}")
                time.sleep(1.0)

        log.info("✅ Worker stopped")
        self.log_stats()

    def _handle_stop(self, sig, frame):
        log.info(f"Signal {sig} → stopping...")
        self.stop = True


if __name__ == "__main__":
    w = ABSAWorker()
    
    # Optional one-shot backfill (uncomment and adapt months):
    # w.backfill_emotions_flat(['2025-10','2025-11','2025-12'])
    
    w.run()
