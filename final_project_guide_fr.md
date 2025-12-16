# 🚀 PROJET MASTODON ABSA V2 - GUIDE COMPLET TEMPS RÉEL

**Version:** 2.0 Optimisée  
**Date:** Décembre 2025  
**Statut:** ✅ Production Ready

---

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture du système](#architecture)
3. [Rôles des 3 membres](#rôles)
4. [Installation et démarrage](#installation)
5. [Configuration du filtrage](#configuration)
6. [Guide d'utilisation](#utilisation)
7. [Monitoring et stats](#monitoring)
8. [Kibana Dashboard](#kibana)
9. [Troubleshooting](#troubleshooting)

---

## 📊 Vue d'ensemble

### Qu'est-ce que c'est?

Un système **temps réel** d'analyse de sentiments par aspect (ABSA) pour les toots Mastodon:

- **Collecte**: Streaming en temps réel depuis Mastodon Public Timeline
- **Traitement**: Analyse ABSA complète (extraction d'aspects, sentiments, émotions, topics)
- **Détection avancée**: Ton critique, métaphores, signaux ironiques
- **Indexation**: Elasticsearch 8.11 pour recherche instantanée
- **Visualisation**: Kibana dashboards en temps réel
- **Filtrage configurable**: 3 modes (strict/balanced/permissive)

### Performance

```
⏱️  Latence end-to-end: 300-700ms
📈 Débit: 50-150 toots/min
💾 Mémoire: ~500MB-2GB (selon mode)
🔋 CPU: 30-70% (1-2 cores)
```

### Technologie

- **Mastodon API**: Streaming temps réel
- **Redis**: File d'attente distribuée
- **Python**: NLP avec spaCy + Transformers
- **Elasticsearch 8.11**: Indexation full-text
- **Kibana**: Dashboards visuels
- **Docker**: Déploiement containerisé

---

## 🏗️ Architecture

### Pipeline complet

```
┌─────────────────────────────────────────────────────────────┐
│                   MASTODON PUBLIC TIMELINE                   │
│              (100M+ toots/jour en 100+ langues)              │
└────────────────────────┬────────────────────────────────────┘
                         │ API Streaming
                         ↓
            ┌──────────────────────────┐
            │   PRODUCER (Membre 1)    │
            │  mastodon_stream.py      │
            │                          │
            │ • Streaming temps réel   │
            │ • Filtrage hashtags      │
            │ • Nettoyage HTML         │
            │ • Extraction metadata    │
            └──────────┬───────────────┘
                       │ JSON
                       ↓
            ┌──────────────────────────┐
            │   REDIS QUEUE            │
            │  mastodon_queue          │
            │  (buffer distribué)      │
            │                          │
            │ • FIFO processing        │
            │ • Persistance optionelle │
            │ • Multi-consumer ready   │
            └──────────┬───────────────┘
                       │ BLPOP
                       ↓
            ┌──────────────────────────┐
            │  WORKER ABSA V2 (M2)     │
            │ worker_absa_optimized_v2│
            │                          │
            │ • Extraction aspects     │
            │ • Analyse sentiments     │
            │ • Détection émotions     │
            │ • Détection ton critique│
            │ • Classification topics  │
            │ • Filtrage configurable │
            │ • Stats détaillées       │
            └──────────┬───────────────┘
                       │ Bulk Index
                       ↓
        ┌──────────────────────────────┐
        │  ELASTICSEARCH 8.11          │
        │ mastodon-trends-YYYY-MM     │
        │                              │
        │ • Mapping optimisé           │
        │ • Nested queries             │
        │ • Full-text search           │
        │ • Real-time indexing (1s)   │
        └──────────┬───────────────────┘
                   │ HTTP API
                   ↓
        ┌──────────────────────────────┐
        │  KIBANA 8.11 (Membre 3)      │
        │  Dashboard + Visualisations  │
        │                              │
        │ • Dashboards temps réel      │
        │ • Recherches sauvegardées    │
        │ • Rapports automatisés       │
        │ • Alertes (optionnel)       │
        └──────────────────────────────┘
```

### Flux de données d'UN toot

```
T=0ms:   Toot posté sur Mastodon.social
         "J'aime l'IA au Maroc! #Maroc #IA"

T=50ms:  Producer reçoit
         ↓ filtre #Maroc/#IA → OK
         ↓ nettoie HTML
         ↓ extrait metadata
         → envoie à Redis

T=70ms:  Worker récupère de Redis
         → commence analyse (asyncio)

T=150ms: spaCy extrait aspects
         → ["IA", "Maroc", "aime"]

T=250ms: XLM-RoBERTa analyse sentiments
         → IA: positive (0.92)
         → Maroc: neutral (0.65)

T=350ms: DistilBERT émotions
         → joy: 0.88

T=400ms: Cross-encoder topic
         → tech & AI (0.87)

T=450ms: Tone critic detection
         → neutral (0.15)

T=500ms: ES bulk index
         → document indexé ✓

T=501ms: Kibana rechargement
         → visible dans dashboard

LATENCE TOTALE: ~500ms = TEMPS RÉEL ⚡
```

---

## 👥 Rôles des 3 membres

### 👨‍💼 Membre 1: PRODUCER (Collecte)

**Fichier:** `mastodon_stream.py`  
**Responsabilités:**
- Streamer les toots Mastodon en temps réel
- Filtrer par hashtags configurables
- Nettoyer le HTML et extraire les données
- Envoyer au Redis queue

**À faire:**
```bash
# 1. Créer un compte Mastodon (gratuit)
# 2. Générer un access token (Préférences > Développement)
# 3. Configurer .env avec:
#    MASTODON_INSTANCE_URL=https://mastodon.social
#    MASTODON_ACCESS_TOKEN=votre_token
# 4. Lancer: python mastodon_stream.py
```

**Vérification:**
```bash
docker exec redis redis-cli llen mastodon_queue
# Output: 150+ (nombre de toots en attente)
```

---

### 🔧 Membre 2: WORKER (Analyse ABSA)

**Fichier:** `worker_absa_optimized_v2.py`  
**Responsabilités:**
- Extraire les aspects (spaCy NLP)
- Analyser les sentiments (XLM-RoBERTa)
- Détecter les émotions (DistilBERT)
- Déterminer le ton critique (patterns avancés)
- Classer les topics (Cross-encoder)
- Indexer dans Elasticsearch

**À faire:**
```bash
# 1. Installer les dépendances:
pip install spacy transformers torch elasticsearch

# 2. Télécharger les modèles:
python -m spacy download en_core_web_sm
python -m spacy download fr_core_news_sm

# 3. Configurer le mode de filtrage:
python configure_filter_mode.py
# Choix: strict (qualité max) / balanced (recommandé) / permissive (volume max)

# 4. Lancer le worker:
FILTER_MODE=balanced python worker_absa_optimized_v2.py
```

**Vérification:**
```bash
tail -f worker_absa_v2.log
# Doit afficher: "Processed: X | Indexed: Y | Errors: Z"
```

---

### 📊 Membre 3: DASHBOARD (Visualisation)

**Outils:** Kibana 8.11  
**Responsabilités:**
- Créer les index patterns Elasticsearch
- Construire des dashboards en temps réel
- Implémenter les recherches sauvegardées
- Générer des rapports d'analyse
- Configurer les alertes (optionnel)

**À faire:**
```bash
# 1. Ouvrir Kibana
start http://localhost:5601

# 2. Créer un Index Pattern
Stack Management → Index Patterns → Create
Pattern: mastodon-trends-*
Time field: timestamp

# 3. Créer le Dashboard
Dashboards → Create Dashboard
Name: "ABSA Real-time Analysis"

# 4. Ajouter les visualisations
(voir section Kibana ci-dessous)
```

---

## 🚀 Installation et démarrage

### Prérequis

- Docker + Docker Compose
- Python 3.8+
- 4GB RAM minimum
- Compte Mastodon avec token d'accès

### Étape 1: Cloner/Créer les fichiers

Préparez ces fichiers dans un dossier `ProjetNoSQL/`:

```
ProjetNoSQL/
├── docker-compose.yml          # Services Docker
├── mastodon_stream.py           # Producer (Membre 1)
├── worker_absa_optimized_v2.py # Worker (Membre 2)
├── startup_realtime_v2.py       # Démarrage automatique
├── configure_filter_mode.py     # Configuration filtrage
├── .env                         # Credentials (à créer)
└── data/                        # Volumes persistants
    ├── elasticsearch/
    ├── redis/
    └── kibana/
```

### Étape 2: Créer le fichier .env

```bash
# .env
MASTODON_INSTANCE_URL=https://mastodon.social
MASTODON_ACCESS_TOKEN=votre_token_ici
REDIS_URL=redis://localhost:6379
QUEUE_NAME=mastodon_queue
ES_HOST=http://localhost:9200
ES_INDEX_PREFIX=mastodon-trends
FILTER_MODE=balanced
```

### Étape 3: Démarrer l'infrastructure

```bash
# Démarrer Redis + Elasticsearch + Kibana
docker-compose up -d

# Vérifier la santé
docker ps
curl http://localhost:9200/_cluster/health
```

### Étape 4: Installer les dépendances Python

```bash
pip install -r requirements.txt

# Ou manuellement:
pip install redis mastodon.py transformers torch spacy elasticsearch requests loguru psutil

# Télécharger les modèles spaCy:
python -m spacy download en_core_web_sm
python -m spacy download fr_core_news_sm
```

### Étape 5: Configurer le filtrage

```bash
python configure_filter_mode.py

# Choisir: 1=strict, 2=balanced (recommandé), 3=permissive
# Cela crée un .env mis à jour + script de démarrage
```

### Étape 6: Démarrer le pipeline

**Option A: Démarrage automatique (recommandé)**
```bash
python startup_realtime_v2.py
```

**Option B: Démarrage manuel**
```bash
# Terminal 1
python mastodon_stream.py

# Terminal 2
python worker_absa_optimized_v2.py

# Terminal 3
start http://localhost:5601  # Kibana
```

### Étape 7: Vérifier que ça marche

```bash
# Vérifier Redis a des toots
docker exec redis redis-cli llen mastodon_queue

# Vérifier Elasticsearch indexe
curl http://localhost:9200/mastodon-trends-*/_count

# Voir les logs du Worker
tail -f worker_absa_v2.log

# Ouvrir Kibana
start http://localhost:5601
```

---

## ⚙️ Configuration du filtrage

### 3 modes disponibles

#### Mode 1: STRICT
```
Longueur minimum: 3 caractères
POS autorisés: NOUN, PROPN, ADJ
Stopwords: Liste étendue
Répétitions max: 6
Taux de filtrage: 85-90%

✅ Aspect: "intelligence"
❌ Aspect: "ai" (trop court)
❌ Aspect: "très" (stopword)

Usage: Analyses précises, articles académiques
```

#### Mode 2: BALANCED ⭐ Recommandé
```
Longueur minimum: 2 caractères
POS autorisés: NOUN, PROPN, ADJ, VERB
Stopwords: Liste minimale
Répétitions max: 10
Taux de filtrage: 70-80%

✅ Aspect: "intelligence"
✅ Aspect: "ai"
✅ Aspect: "aimer"
❌ Aspect: "être" (stopword)

Usage: Équilibre qualité/volume (RECOMMANDÉ)
```

#### Mode 3: PERMISSIVE
```
Longueur minimum: 2 caractères
POS autorisés: NOUN, PROPN, ADJ, VERB, ADV
Stopwords: Liste minimale
Répétitions max: 15
Taux de filtrage: 60-70%

✅ Aspect: "intelligence"
✅ Aspect: "ai"
✅ Aspect: "aimer"
✅ Aspect: "très" (adverbe)
❌ Aspect: "être" (stopword)

Usage: Exploration, volume maximal
```

### Changer le mode

```bash
# Arrêter le pipeline
Ctrl+C

# Reconfigurer
python configure_filter_mode.py

# Relancer
python startup_realtime_v2.py
```

---

## 📖 Guide d'utilisation

### Démarrer le pipeline complet

```bash
# Automatiquement
python startup_realtime_v2.py

# Ou manuellement
python mastodon_stream.py &
python worker_absa_optimized_v2.py &
start http://localhost:5601
```

### Vérifier les performances

```bash
# Nombre de documents indexés
curl http://localhost:9200/mastodon-trends-*/_count
# Output: {"count": 182}

# Top 10 aspects
curl -X POST "http://localhost:9200/mastodon-trends-*/_search" \
  -H 'Content-Type: application/json' \
  -d'{"aggs": {"top_aspects": {"terms": {"field": "aspects", "size": 10}}},"size": 0}'

# Distribution sentiments
curl -X POST "http://localhost:9200/mastodon-trends-*/_search" \
  -H 'Content-Type: application/json' \
  -d'{"aggs": {"sentiments": {"terms": {"field": "sentiment.label"}}},"size": 0}'

# Tous les toots avec ton critique
curl -X POST "http://localhost:9200/mastodon-trends-*/_search" \
  -H 'Content-Type: application/json' \
  -d'{"query": {"term": {"critical_tone.tone": "critical"}}, "size": 50}'
```

### Exporter les données

```bash
# En JSON Lines
curl http://localhost:9200/mastodon-trends-*/_search?scroll=1m | \
  jq '.hits.hits[] | ._source' > export.jsonl

# En CSV (depuis Kibana)
Dashboards → Export → CSV

# En PDF (depuis Kibana)
Dashboards → Export → PDF
```

---

## 📊 Monitoring et stats

### Logs du Worker

```bash
# Voir tous les logs
tail -f worker_absa_v2.log

# Filtrer les erreurs
grep "ERROR\|✗" worker_absa_v2.log

# Stats en temps réel (toutes les 20 toots)
grep "Processed:" worker_absa_v2.log
```

### Stats disponibles

```
Processed: 150       # Toots reçus de Redis
Indexed: 145         # Toots indexés dans ES
Errors: 0            # Erreurs de traitement

Aspects Found: 850   # Aspects extraits (avant filtrage)
Aspects Filtered: 150 # Aspects rejetés (raisons listées)

Filter Reasons:
  • stopword: 45 (30%) - Mot vide (être, avoir, le, etc)
  • too_short: 35 (23%) - Moins de N caractères
  • wrong_pos: 40 (27%) - Part-of-speech non autorisé
  • url_or_mention: 20 (13%) - Lien ou @mention
  • too_repetitive: 10 (7%) - Répété > max

Critical Tone: 12    # Toots avec ton critique détecté
Skeptical Tone: 8    # Toots avec ton skeptique
```

### Dashboard Monitoring

Dans Kibana, créer une visualization "Metric" pour:
- Nombre total de documents: `COUNT`
- Nombre de documents/min: `RATE(COUNT)`
- Nombre d'erreurs: `COUNT(errors)`

---

## 🎨 Kibana Dashboard

### Créer l'Index Pattern

1. Ouvrir Kibana: http://localhost:5601
2. Stack Management → Index Patterns
3. Create Index Pattern
4. Nom: `mastodon-trends-*`
5. Time Field: `timestamp`
6. Créer

### Créer le Dashboard

1. Dashboards → Create Dashboard
2. Nommer: "ABSA Real-time Analysis"

### Ajouter les visualisations

#### Viz 1: Total Documents (Metric)
```
Type: Metric
Index: mastodon-trends-*
Metric: Count
Title: "Total Documents Analyzed"
```

#### Viz 2: Top Aspects (Pie)
```
Type: Pie Chart
Index: mastodon-trends-*
Aggregation: Terms → aspects (size: 15)
Title: "Top Aspects Discussed"
```

#### Viz 3: Sentiments (Bar)
```
Type: Bar Chart
Index: mastodon-trends-*
X-axis: Terms → sentiment.label
Y-axis: Count
Title: "Sentiment Distribution"
```

#### Viz 4: Critical Tone (Pie)
```
Type: Pie Chart
Index: mastodon-trends-*
Aggregation: Terms → critical_tone.tone
Title: "Tone Detection"
```

#### Viz 5: Timeline (Line)
```
Type: Line Chart
Index: mastodon-trends-*
X-axis: Date Histogram → timestamp (auto interval)
Y-axis: Count
Title: "Documents Over Time"
```

#### Viz 6: Top Languages (Pie)
```
Type: Pie Chart
Index: mastodon-trends-*
Aggregation: Terms → language
Title: "Languages Detected"
```

### Recherches sauvegardées

#### Recherche 1: Sentiments positifs
```json
{
  "query": {
    "term": {"sentiment.label": "positive"}
  }
}
```
Nom: "Positive Sentiments"

#### Recherche 2: Ton critique
```json
{
  "query": {
    "term": {"critical_tone.tone": "critical"}
  }
}
```
Nom: "Critical Tone Detected"

#### Recherche 3: Aspect spécifique
```json
{
  "query": {
    "match": {"aspects": "produit"}
  }
}
```
Nom: "All mentions of 'produit'"

---

## 🆘 Troubleshooting

### Redis

```bash
# Redis ne répond pas
docker restart redis
docker logs redis

# Vider la queue Redis
docker exec redis redis-cli FLUSHDB
```

### Elasticsearch

```bash
# Cluster RED
docker restart elasticsearch
sleep 30
curl http://localhost:9200/_cluster/health

# Supprimer un index problématique
curl -X DELETE "http://localhost:9200/mastodon-trends-2025-12"
```

### Worker ne traite rien

```bash
# Vérifier que Redis a des toots
docker exec redis redis-cli llen mastodon_queue

# Vérifier le Worker tourne
ps aux | grep worker_absa

# Voir les erreurs
tail -f worker_absa_v2.log | grep ERROR
```

### Kibana ne voit pas les données

```bash
# Attendre 30 secondes que ES indexe
sleep 30

# Rafraîchir l'Index Pattern
Stack Management → Index Patterns → mastodon-trends-* → Refresh
```

### Latence élevée

```bash
# Vérifier la mémoire
docker stats

# Réduire la mémoire ES dans docker-compose.yml
"ES_JAVA_OPTS=-Xms256m -Xmx256m"

# Utiliser le mode STRICT pour moins de calculs
FILTER_MODE=strict python worker_absa_optimized_v2.py
```

---

## 📚 Ressources

- **Elasticsearch Documentation**: https://www.elastic.co/guide/en/elasticsearch/reference/
- **Kibana Guide**: https://www.elastic.co/guide/en/kibana/
- **spaCy Documentation**: https://spacy.io/
- **Transformers Library**: https://huggingface.co/transformers/
- **Mastodon API**: https://docs.joinmastodon.org/

---

## 🎯 Checklist final

- [ ] Docker Compose démarré (Redis, ES, Kibana)
- [ ] Producer (mastodon_stream.py) actif
- [ ] Worker (worker_absa_optimized_v2.py) actif
- [ ] Redis queue a des toots (`redis-cli llen mastodon_queue`)
- [ ] Elasticsearch cluster is GREEN/YELLOW
- [ ] Documents indexés dans ES (`curl http://localhost:9200/mastodon-trends-*/_count`)
- [ ] Kibana accessible (http://localhost:5601)
- [ ] Index Pattern créé (mastodon-trends-*)
- [ ] Dashboard créé avec visualisations
- [ ] Premier toot visible dans Discover

---

## 📞 Support et contact

| Rôle | Responsable | Contact |
|------|-------------|---------|
| Producer | Membre 1 | mastodon_stream.py |
| Worker/ABSA | Membre 2 | worker_absa_optimized_v2.py |
| Dashboard/Kibana | Membre 3 | kibana |

---

**Bon courage! 🚀** 

Le système est prêt pour la production. Commencez avec le mode **BALANCED** (recommandé) et ajustez selon vos besoins!