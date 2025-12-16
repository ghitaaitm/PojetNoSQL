"""
WORKER ABSA V2 - VERSION AVEC FILTRAGE CONFIGURABLE
Mode BALANCED par défaut (filtrage ~70-80%)
"""

import redis
import json
import time
import signal
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import logging
import sys
import os
import re
from collections import defaultdict

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ================================================
# LOGGING CONFIGURATION
# ================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('worker_absa_v2.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ================================================
# CONFIGURATION
# ================================================
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
QUEUE_NAME = os.getenv('QUEUE_NAME', 'mastodon_queue')
ES_HOST = os.getenv('ES_HOST', 'http://localhost:9200')
ES_INDEX_PREFIX = os.getenv('ES_INDEX_PREFIX', 'mastodon-trends')
BLPOP_TIMEOUT = 1

# Mode de filtrage (strict, balanced, permissive)
FILTER_MODE = os.getenv('FILTER_MODE', 'balanced').lower()

# ================================================
# CONFIGURATIONS DE FILTRAGE
# ================================================
FILTER_CONFIGS = {
    'strict': {
        'min_aspect_length': 3,
        'max_repetitions': 6,
        'allowed_pos': {"NOUN", "PROPN", "ADJ"},
        'use_extended_stopwords': True,
        'description': 'Filtrage strict - Qualité maximale'
    },
    'balanced': {
        'min_aspect_length': 2,
        'max_repetitions': 10,
        'allowed_pos': {"NOUN", "PROPN", "ADJ", "VERB"},
        'use_extended_stopwords': False,
        'description': 'Filtrage équilibré - Recommandé'
    },
    'permissive': {
        'min_aspect_length': 2,
        'max_repetitions': 15,
        'allowed_pos': {"NOUN", "PROPN", "ADJ", "VERB", "ADV"},
        'use_extended_stopwords': False,
        'description': 'Filtrage permissif - Volume maximal'
    }
}

# Récupérer la config du mode choisi
CURRENT_CONFIG = FILTER_CONFIGS.get(FILTER_MODE, FILTER_CONFIGS['balanced'])


class CriticalToneDetector:
    """Advanced critical tone detector - multilingual"""
    
    def __init__(self):
        self.critical_metaphors = {
            'feeding the machine': 'critique_exploitation',
            'race to the bottom': 'critique_economique',
            'surveillance capitalism': 'critique_privacy',
            'digital sweatshop': 'critique_labor',
            'gig economy': 'critique_precarity',
            'algorithm bias': 'critique_fairness',
            'tech bro': 'critique_culture',
            'move fast and break things': 'critique_recklessness',
            'disruption': 'critique_buzzword',
            'innovation theater': 'critique_fake_progress',
            'dark pattern': 'critique_manipulation',
            'attention economy': 'critique_exploitation',
            'platform capitalism': 'critique_economique',
            'precarious work': 'critique_labor',
            'capitalisme de surveillance': 'critique_privacy',
            'économie de l\'attention': 'critique_exploitation',
            'ubérisation': 'critique_precarity',
            'start-up nation': 'critique_politique',
            'travail précaire': 'critique_precarity',
            'greenwashing': 'critique_fake_progress',
        }
        
        self.irony_quote_patterns = [
            r'[«»]([^«»]+)[«»]',
            r'"([^"]+)"',
            r"'([^']+)'",
        ]
        
        self.critique_keywords = {
            'exploitation', 'exploitative', 'precarious', 'underpaid', 'overworked',
            'dystopian', 'orwellian', 'monopoly', 'inequality', 'unfair', 'biased',
            'discriminatory', 'problematic', 'backlash', 'scandal', 'extractive',
            'exploité', 'exploités', 'précaire', 'précarité', 'sous-payé',
            'dystopique', 'orwellien', 'monopole', 'inégalité', 'injustice',
        }
        
        self.critical_emojis = {
            '🙄', '😒', '🤨', '😤', '😠', '😡', '🤬', '💀', '☠️', '🤡',
            '🚩', '⚠️', '🔴', '❌', '💩', '🤮', '😬', '🫠'
        }
    
    def analyze_critical_tone(self, text: str) -> Dict:
        """Main critical tone analysis"""
        text_lower = text.lower()
        critical_score = 0.0
        signals = []
        
        # Detect metaphors
        for metaphor in self.critical_metaphors:
            if metaphor in text_lower:
                critical_score += 0.4
                signals.append(f"metaphor:{metaphor[:30]}")
                break
        
        # Detect critique keywords
        keyword_count = sum(1 for kw in self.critique_keywords if kw in text_lower)
        if keyword_count > 0:
            critical_score += min(0.5, keyword_count * 0.15)
            signals.append(f"keywords:{keyword_count}")
        
        # Detect emojis
        emoji_count = sum(text.count(emoji) for emoji in self.critical_emojis)
        if emoji_count > 0:
            critical_score += min(0.3, emoji_count * 0.1)
            signals.append(f"emoji:{emoji_count}")
        
        # Determine tone
        if critical_score >= 0.65:
            tone = 'critical'
        elif critical_score >= 0.45:
            tone = 'skeptical'
        elif critical_score >= 0.25:
            tone = 'questioning'
        else:
            tone = 'neutral'
        
        return {
            'tone': tone,
            'critical_score': round(critical_score, 3),
            'signals': signals
        }


class ABSAWorker:
    """Main ABSA Worker V2 with configurable filtering"""
    
    def __init__(self):
        logger.info("=" * 80)
        logger.info("WORKER ABSA V2 - INITIALIZING")
        logger.info("=" * 80)
        logger.info(f"🔧 Filter mode: {FILTER_MODE.upper()} - {CURRENT_CONFIG['description']}")
        logger.info(f"   Min length: {CURRENT_CONFIG['min_aspect_length']} chars")
        logger.info(f"   Max repetitions: {CURRENT_CONFIG['max_repetitions']}")
        logger.info(f"   Allowed POS: {', '.join(CURRENT_CONFIG['allowed_pos'])}")
        logger.info("=" * 80)
        
        self.redis_client = self._init_redis()
        self.es_client = self._init_elasticsearch()
        
        self.nlp_models = {}
        self.sentiment_model = None
        self.emotion_model = None
        
        self.tone_detector = CriticalToneDetector()
        self.should_stop = False
        
        # Stopwords selon le mode
        if CURRENT_CONFIG['use_extended_stopwords']:
            self.stopwords = {
                'être', 'avoir', 'faire', 'dire', 'aller', 'pouvoir', 'voir',
                'donner', 'prendre', 'venir', 'devoir', 'vouloir', 'savoir',
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                'for', 'of', 'with', 'from', 'by', 'about', 'as', 'into',
            }
        else:
            # Liste minimale pour BALANCED/PERMISSIVE
            self.stopwords = {
                'être', 'avoir', 'faire', 'the', 'a', 'an', 'and', 'or'
            }
        
        self.url_pattern = re.compile(r'https?://[^\s]+|www\.[^\s]+|t\.co/[^\s]+', re.IGNORECASE)
        self.mention_pattern = re.compile(r'@[\w]+')
        
        self.stats = {
            'processed': 0, 'errors': 0, 'indexed': 0,
            'aspects_found': 0, 'aspects_filtered': 0,
            'filter_reasons': defaultdict(int),  # NEW: Track filtering reasons
            'critical_tone_detected': 0, 'skeptical_tone_detected': 0,
            'start_time': datetime.now(),
        }
        
        logger.info("✓ Worker V2 initialized successfully\n")
    
    def _init_redis(self) -> redis.Redis:
        """Initialize Redis connection"""
        try:
            client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                retry_on_timeout=True
            )
            client.ping()
            logger.info("✓ Redis connected")
            return client
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    def _init_elasticsearch(self):
        """Initialize Elasticsearch connection"""
        try:
            from elasticsearch import Elasticsearch
            es = Elasticsearch(
                [ES_HOST],
                request_timeout=15,
                max_retries=3,
                retry_on_timeout=True,
                verify_certs=False,
                ssl_show_warn=False
            )
            if es.ping():
                logger.info("✓ Elasticsearch connected")
                return es
            else:
                logger.warning("Elasticsearch ping failed")
                return None
        except Exception as e:
            logger.warning(f"Elasticsearch unavailable: {e}")
            return None
    
    def _init_spacy(self, lang: str = 'fr'):
        """Initialize spaCy model"""
        lang = (lang or 'fr').lower()
        if lang in self.nlp_models:
            return self.nlp_models[lang]
        
        try:
            import spacy
            lang_models = {
                'fr': 'fr_core_news_sm',
                'en': 'en_core_web_sm',
                'es': 'es_core_news_sm',
                'de': 'de_core_news_sm',
            }
            model_name = lang_models.get(lang, 'en_core_web_sm')
            
            try:
                nlp = spacy.load(model_name)
            except OSError:
                logger.warning(f"Model {model_name} not found → fallback en")
                nlp = spacy.load("en_core_web_sm")
                lang = 'en'
            
            self.nlp_models[lang] = nlp
            logger.info(f"✓ spaCy {lang.upper()} loaded")
            return nlp
        except Exception as e:
            logger.error(f"spaCy error: {e}")
            return None
    
    def _init_sentiment_model(self):
        """Initialize sentiment model"""
        if self.sentiment_model:
            return self.sentiment_model
        try:
            from transformers import pipeline
            logger.info("Loading sentiment model...")
            self.sentiment_model = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual",
                device=-1,
                truncation=True,
                max_length=512
            )
            logger.info("✓ Sentiment model loaded")
            return self.sentiment_model
        except Exception as e:
            logger.error(f"Sentiment model failed: {e}")
            return None
    
    def is_valid_aspect(self, token, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate aspect token with reason tracking
        Returns: (is_valid, filter_reason)
        """
        if not token or not token.text.strip():
            return False, 'empty'
        
        aspect = token.text.strip().lower()
        
        # Check length
        if len(aspect) < CURRENT_CONFIG['min_aspect_length']:
            return False, 'too_short'
        
        # Check URLs/mentions
        if self.url_pattern.match(aspect) or self.mention_pattern.match(aspect):
            return False, 'url_or_mention'
        
        # Check stopwords
        if aspect in self.stopwords:
            return False, 'stopword'
        
        # Check POS
        if token.pos_ not in CURRENT_CONFIG['allowed_pos']:
            return False, 'wrong_pos'
        
        # Check alphanumeric
        if not re.search(r'[a-zA-ZÀ-ÿ]', aspect):
            return False, 'no_alpha'
        
        # Check repetitions
        if text.lower().count(aspect) > CURRENT_CONFIG['max_repetitions']:
            return False, 'too_repetitive'
        
        return True, None
    
    def extract_aspects(self, text: str, lang: str) -> List[str]:
        """Extract aspects with filtering stats"""
        aspects = set()
        nlp = self._init_spacy(lang)
        if not nlp:
            return []
        
        try:
            doc = nlp(text)
            for token in doc:
                is_valid, reason = self.is_valid_aspect(token, text)
                if is_valid:
                    aspects.add(token.lemma_.lower())
                    self.stats['aspects_found'] += 1
                else:
                    self.stats['aspects_filtered'] += 1
                    if reason:
                        self.stats['filter_reasons'][reason] += 1
            
            return list(aspects)
        except Exception as e:
            logger.error(f"Aspect extraction error: {e}")
            return []
    
    def analyze_sentiment(self, text: str, critical_tone: Dict) -> Dict:
        """Analyze sentiment"""
        model = self._init_sentiment_model()
        if not model:
            return {"label": "neutral", "score": 0.0}
        
        try:
            result = model(text[:512])[0]
            label = result["label"].lower()
            score = result["score"]
            
            # Invert if strong irony
            if critical_tone["critical_score"] >= 0.7 and label in ["positive", "pos"]:
                label = "critical_ironic"
            
            return {"label": label, "score": round(score, 3)}
        except Exception as e:
            logger.error(f"Sentiment error: {e}")
            return {"label": "neutral", "score": 0.0}
    
    def analyze_absa(self, toot: Dict) -> Optional[Dict]:
        """Main ABSA analysis"""
        text = toot.get("text", "").strip()
        lang = toot.get("lang", "fr")
        
        if not text:
            return None
        
        # Analyze tone
        critical_tone = self.tone_detector.analyze_critical_tone(text)
        
        if critical_tone["tone"] == "critical":
            self.stats['critical_tone_detected'] += 1
        elif critical_tone["tone"] == "skeptical":
            self.stats['skeptical_tone_detected'] += 1
        
        # Extract aspects
        aspects = self.extract_aspects(text, lang)
        
        # Only index if aspects found
        if not aspects:
            return None
        
        # Analyze sentiment
        sentiment = self.analyze_sentiment(text, critical_tone)
        
        return {
            "id": toot.get("toot_id"),
            "created_at": toot.get("created_at"),
            "language": lang,
            "text": text,
            "aspects": aspects,
            "sentiment": sentiment,
            "critical_tone": critical_tone,
            "metadata": {
                "hashtags": toot.get("hashtags", []),
                "author": toot.get("author_username"),
                "instance": toot.get("instance")
            }
        }
    
    def process_toot(self, toot_json: str):
        """Process a single toot"""
        try:
            toot = json.loads(toot_json)
            result = self.analyze_absa(toot)
            
            if result and self.es_client:
                index_name = f"{ES_INDEX_PREFIX}-{datetime.utcnow():%Y-%m}"
                try:
                    self.es_client.index(index=index_name, document=result)
                    self.stats['indexed'] += 1
                except Exception as e:
                    logger.error(f"ES indexing error: {e}")
                    self.stats['errors'] += 1
            
            self.stats['processed'] += 1
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Processing error: {e}")
    
    def log_stats(self):
        """Log detailed statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        total_aspects = self.stats['aspects_found'] + self.stats['aspects_filtered']
        kept_pct = (self.stats['aspects_found'] / total_aspects * 100) if total_aspects > 0 else 0
        filtered_pct = (self.stats['aspects_filtered'] / total_aspects * 100) if total_aspects > 0 else 0
        
        logger.info("=" * 70)
        logger.info(f"📊 STATS [{FILTER_MODE.upper()}] - Uptime: {uptime:.0f}s")
        logger.info("=" * 70)
        logger.info(f"✅ Processed: {self.stats['processed']} | "
                   f"Indexed: {self.stats['indexed']} | "
                   f"Errors: {self.stats['errors']}")
        logger.info(f"🔍 Aspects: Found={self.stats['aspects_found']} ({kept_pct:.1f}% kept) | "
                   f"Filtered={self.stats['aspects_filtered']} ({filtered_pct:.1f}%)")
        
        # Show filtering reasons
        if self.stats['filter_reasons']:
            logger.info("📋 Raisons de filtrage:")
            total_filtered = sum(self.stats['filter_reasons'].values())
            for reason, count in sorted(self.stats['filter_reasons'].items(), 
                                       key=lambda x: x[1], reverse=True):
                pct = (count / total_filtered * 100) if total_filtered > 0 else 0
                logger.info(f"  • {reason:20s}: {count:6d} ({pct:5.1f}%)")
        
        logger.info(f"🎭 Tone: Critical={self.stats['critical_tone_detected']} | "
                   f"Skeptical={self.stats['skeptical_tone_detected']}")
        logger.info("=" * 70)
    
    def run(self):
        """Main worker loop"""
        logger.info(f"Worker ABSA V2 started [Mode: {FILTER_MODE.upper()}] – waiting for messages...")
        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)
        
        stat_counter = 0
        
        while not self.should_stop:
            try:
                item = self.redis_client.blpop(QUEUE_NAME, timeout=BLPOP_TIMEOUT)
                if item:
                    _, toot_json = item
                    self.process_toot(toot_json)
                    
                    stat_counter += 1
                    if stat_counter % 20 == 0:
                        self.log_stats()
                        stat_counter = 0
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(1)
        
        logger.info("Worker stopped gracefully")
        self.log_stats()
    
    def _handle_stop(self, sig, frame):
        """Handle shutdown signal"""
        logger.info(f"Signal {sig} received → shutting down...")
        self.should_stop = True


if __name__ == "__main__":
    try:
        worker = ABSAWorker()
        worker.run()
    except KeyboardInterrupt:
        logger.info("Manual stop (Ctrl+C)")
    except Exception as e:
        logger.exception("Fatal crash")
        sys.exit(1)