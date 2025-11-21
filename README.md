# PROJET NOSQL - PIPELINE D'INGESTION MASTODON

**Membre 1 : Infrastructure + Collecte Mastodon + File d'attente Redis**

Ce projet fait partie d'un système plus large qui collecte, analyse et visualise des toots Mastodon en temps réel.

---

## TABLE DES MATIÈRES

1. [Vue d'ensemble](#vue-densemble)
2. [Prérequis](#prérequis)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Utilisation](#utilisation)
6. [Validation](#validation)
7. [Structure du projet](#structure-du-projet)
8. [Dépannage](#dépannage)

---

## VUE D'ENSEMBLE

Cette partie du projet (Membre 1) est responsable de :

1. **Infrastructure** : Mise en place de Docker avec Elasticsearch, Kibana et Redis
2. **Collecte Mastodon** : Streaming de toots Mastodon en temps réel via l'API Mastodon (WebSocket)
3. **File d'attente** : Envoi des toots dans Redis pour traitement par le Membre 2

### Pipeline

```
Mastodon API (Streaming temps réel) → mastodon_stream.py → Redis Queue → (Membre 2 : Analyse)
```

---

## PRÉREQUIS

### Logiciels nécessaires

- **Docker Desktop** : Pour exécuter les conteneurs
  - Télécharger : https://www.docker.com/products/docker-desktop/
  - Vérifier l'installation : `docker --version`
  
- **Docker Compose** : Inclus avec Docker Desktop
  - Vérifier : `docker compose version`

- **Python 3.8+** : Pour exécuter les scripts Python
  - Vérifier : `python --version`

- **Git** (optionnel) : Pour versionner le projet

### Compte Mastodon (GRATUIT et streaming temps réel !)

✅ **EXCELLENTE NOUVELLE : Mastodon API est 100% GRATUITE et supporte le streaming temps réel !**

Avantages de Mastodon :
- ✅ **100% Gratuit** (pas de limitations)
- ✅ **Streaming temps réel** via WebSocket (pas de polling !)
- ✅ **Sans restrictions** de compte ou d'applications
- ✅ **Réseau décentralisé** : choisis ton instance (mastodon.social, mastodon.art, etc.)
- ✅ **API simple** : pas besoin de Devvit ou de processus complexe

**Pour créer une application Mastodon :**
1. **Choisis une instance Mastodon** (tu peux en créer un compte gratuitement) :
   - **mastodon.social** : Instance populaire et générale
   - **mastodon.art** : Pour l'art
   - **mastodon.online** : Instance générale
   - Ou cherche d'autres instances : https://joinmastodon.org/servers
2. **Crée un compte** sur l'instance choisie (gratuit)
3. **Va dans Préférences > Développement > Nouvelles applications**
4. **Crée une application** :
   - **Nom** : "NoSQL Project"
   - **Permissions** : cocher uniquement **"read"** (lecture seule)
   - **Redirection** : laisser vide ou `http://localhost:8080`
5. **Copie l'Access Token** généré (tu ne pourras plus le voir après !)
6. **Note l'URL de l'instance** (ex: `https://mastodon.social`)

---

## INSTALLATION

### Étape 1 : Cloner ou télécharger le projet

```bash
# Si tu utilises Git
git clone <url-du-repo>
cd "NoSQL Project"

# Sinon, extrais l'archive dans un dossier
```

### Étape 2 : Installer les dépendances Python

```bash
# Créer un environnement virtuel (recommandé)
python -m venv venv

# Activer l'environnement virtuel
# Sur Windows PowerShell :
.\venv\Scripts\Activate.ps1

# Sur Windows CMD :
venv\Scripts\activate.bat

# Installer les dépendances
pip install -r requirements.txt
```

### Étape 3 : Créer le fichier de configuration

```bash
# Copier le fichier d'exemple
copy env.example .env

# OU sur Linux/Mac :
# cp env.example .env
```

### Étape 4 : Configurer les credentials Mastodon

1. Ouvre le fichier `.env` avec un éditeur de texte
2. Remplace les valeurs par tes vraies credentials Mastodon :
   ```
   MASTODON_INSTANCE_URL=https://mastodon.social
   MASTODON_ACCESS_TOKEN=ton_access_token_ici
   ```
3. Sauvegarde le fichier

**⚠️ IMPORTANT : Ne partage JAMAIS ton fichier .env ! Il contient des informations sensibles.**

---

## CONFIGURATION

### Fichier docker-compose.yml

Le fichier `docker-compose.yml` configure 3 services :

- **Elasticsearch** : Port 9200 (base de données)
- **Kibana** : Port 5601 (interface web)
- **Redis** : Port 6379 (file d'attente)

### Fichier .env

Variables d'environnement configurables :

- `MASTODON_INSTANCE_URL` : URL de ton instance Mastodon (OBLIGATOIRE - ex: `https://mastodon.social`)
- `MASTODON_ACCESS_TOKEN` : Access Token de ton application Mastodon (OBLIGATOIRE)
- `REDIS_URL` : URL de connexion Redis (par défaut : `redis://localhost:6379`)
- `REDIS_QUEUE_NAME` : Nom de la queue Redis (par défaut : `mastodon_queue`)

---

## UTILISATION

### 1. Démarrer l'infrastructure Docker

```bash
# Démarrer tous les services en arrière-plan
docker compose up -d

# Vérifier que les services tournent
docker ps

# Voir les logs
docker compose logs -f

# Voir les logs d'un service spécifique
docker compose logs -f elasticsearch
docker compose logs -f redis
docker compose logs -f kibana
```

**Vérification que tout fonctionne :**

- Elasticsearch : http://localhost:9200
- Kibana : http://localhost:5601
- Redis : Vérifier avec `docker compose ps`

### 2. Lancer la collecte Twitter

**Choisis ton script selon ce que tu veux :**

#### Option A : Tweets de test (RECOMMANDÉ - gratuit, pas besoin de Bearer Token)

```bash
# Dans le terminal, depuis le dossier du projet
python twitter_stream_mock.py
```

**Ce que fait le script :**
- Génère des tweets fictifs réalistes
- Simule le streaming Twitter
- Normalise chaque tweet en JSON
- Envoie les tweets dans Redis (queue `tweets_queue`)

✅ **Parfait pour tester le pipeline sans payer !**

#### Option B : Vrais tweets (nécessite un accès API payant)

```bash
# Dans le terminal, depuis le dossier du projet
python twitter_stream.py
```

**Ce que fait le script :**
- Se connecte à l'API Twitter
- Écoute les tweets en temps réel selon les hashtags configurés
- Normalise chaque tweet en JSON
- Envoie les tweets dans Redis (queue `tweets_queue`)

**Hashtags suivis par défaut :**
- #Maroc
- #IA
- #Gaza
- #python
- #NoSQL

**Pour modifier les hashtags :**

Édite le fichier correspondant (`twitter_stream.py` ou `twitter_stream_mock.py`), variable `hashtags_to_follow` :

```python
hashtags_to_follow = [
    'Maroc',
    'IA',
    'Gaza',
    # Ajoute tes hashtags ici
]
```

### 3. Vérifier que les toots arrivent dans Redis

**Méthode 1 : Via redis-cli (dans Docker)**

```bash
# Se connecter au conteneur Redis
docker exec -it redis redis-cli

# Voir la taille de la queue
LLEN mastodon_queue

# Voir les 10 premiers toots (sans les supprimer)
LRANGE mastodon_queue 0 9

# Voir un toot au format lisible
LRANGE mastodon_queue 0 0
```

**Méthode 2 : Via le script de validation**

```bash
python validate_pipeline.py
```

Ce script génère un rapport avec :
- La taille de la queue
- Le format des JSON
- 10 exemples de toots collectés
- Un fichier `rapport_validation.md`

### 4. Arrêter le streaming

Dans le terminal où tourne `mastodon_stream.py`, appuie sur :
- **Ctrl+C** pour arrêter proprement

### 5. Arrêter l'infrastructure Docker

```bash
# Arrêter les services (sans supprimer les données)
docker compose stop

# Arrêter ET supprimer les conteneurs (sans les données)
docker compose down

# Arrêter ET supprimer TOUT (données incluses)
docker compose down -v
```

---

## VALIDATION

### Script de validation

Le script `validate_pipeline.py` vérifie que tout fonctionne :

```bash
python validate_pipeline.py
```

**Ce qu'il vérifie :**

1.  Connexion à Redis
2.  Taille de la queue (`mastodon_queue`)
3.  Format JSON des toots (champs obligatoires)
4.  Génération d'un rapport avec 10 toots

**Résultat attendu :**

```
✓ Connexion à Redis réussie
✓ Taille de la queue 'mastodon_queue' : 42 toots
✓ Toots valides : 10
✓ Taux de succès : 100.0%
✓ Rapport généré avec succès
```

**Fichier généré :** `rapport_validation.md`

### Validation manuelle

**Vérifier la connexion Redis :**

```bash
docker exec -it redis redis-cli PING
# Doit répondre : PONG
```

**Vérifier la taille de la queue :**

```bash
docker exec -it redis redis-cli LLEN mastodon_queue
# Doit retourner un nombre (ex: 42)
```

**Voir un toot au format JSON :**

```bash
docker exec -it redis redis-cli LRANGE mastodon_queue 0 0
# Doit afficher un JSON avec les champs : toot_id, text, author_id, instance, etc.
```

---

##  STRUCTURE DU PROJET

```
NoSQL Project/
├── docker-compose.yml          # Configuration Docker (ES, Kibana, Redis)
├── requirements.txt            # Dépendances Python
├── env.example                 # Modèle de fichier .env
├── .env                        # Configuration (à créer - NON COMMITÉ)
├── mastodon_stream.py          # Script de collecte Mastodon (API GRATUITE + Streaming temps réel !)
├── validate_pipeline.py        # Script de validation du pipeline
├── README.md                   # Cette documentation
├── rapport_validation.md       # Rapport généré (après validation)
│
├── data/                       # Volumes Docker (données persistantes)
│   ├── elasticsearch/         # Données Elasticsearch
│   ├── kibana/                # Données Kibana
│   └── redis/                 # Données Redis
│
└── logs/                       # Logs du script Python
    └── mastodon_stream.log     # Logs détaillés
```

---

##  DÉPANNAGE

### Problème : Docker ne démarre pas

**Erreur :** `Cannot connect to the Docker daemon`

**Solution :**
1. Vérifie que Docker Desktop est lancé
2. Attends que Docker Desktop soit complètement démarré
3. Relance `docker compose up -d`

---

### Problème : Elasticsearch ne démarre pas

**Erreur :** `elasticsearch exited with code 78`

**Solution :**
1. Vérifie que les permissions du dossier `data/elasticsearch` sont correctes
2. Sur Linux/Mac : `chmod -R 777 data/elasticsearch`
3. Sur Windows : Vérifie que le dossier n'est pas en lecture seule

**Erreur :** `max virtual memory areas vm.max_map_count [65530] is too low`

**Solution (Linux uniquement) :**
```bash
sudo sysctl -w vm.max_map_count=262144
```

---

### Problème : Mastodon API retourne 401 (Unauthorized)

**Erreur :** `401 Unauthorized` ou `Invalid credentials`

**Solution :**

1. **Vérifie tes credentials dans `.env` :**
   - Assure-toi que `MASTODON_INSTANCE_URL` est correct (ex: `https://mastodon.social`)
   - Assure-toi que `MASTODON_ACCESS_TOKEN` est correct et complet
   - Vérifie qu'il n'y a pas d'espaces avant/après les valeurs

2. **Vérifie que ton application Mastodon existe :**
   - Va sur ton instance Mastodon (ex: https://mastodon.social)
   - Va dans Préférences > Développement > Applications
   - Vérifie que ton application existe et a les permissions "read"

3. **Vérifie l'access token :**
   - L'access token doit commencer par une série de caractères aléatoires
   - Si tu as oublié le token, crée une nouvelle application
   - Assure-toi qu'il n'y a pas de guillemets dans `.env`

---

### Problème : Aucun toot n'arrive dans Redis

**Vérifications :**

1. **Le streaming tourne-t-il ?**
   ```bash
   # Vérifie les logs
   python mastodon_stream.py
   # Doit afficher : "STREAMING ACTIF - Écoute des toots Mastodon en temps réel..."
   ```

2. **L'instance Mastodon fonctionne-t-elle ?**
   - Vérifie que l'instance Mastodon est accessible (ouvre l'URL dans le navigateur)
   - Certaines instances peuvent être en maintenance ou avoir des problèmes
   - Essaie avec une autre instance populaire (mastodon.social, mastodon.art, etc.)

3. **Redis est-il accessible ?**
   ```bash
   docker exec -it redis redis-cli PING
   # Doit répondre : PONG
   ```

4. **Regarde les logs :**
   - Fichier `logs/mastodon_stream.log`
   - Console lors de l'exécution de `mastodon_stream.py`

5. **Vérifie les credentials :**
   - L'access token doit être valide et avoir les permissions "read"
   - L'instance URL doit être au bon format (https://mastodon.social)

---

### Problème : Erreur "Module not found"

**Erreur :** `ModuleNotFoundError: No module named 'tweepy'`

**Solution :**
1. Vérifie que tu es dans l'environnement virtuel : `.\venv\Scripts\Activate.ps1`
2. Réinstalle les dépendances : `pip install -r requirements.txt`
3. Vérifie que pip est à jour : `pip install --upgrade pip`

---

### Problème : Port déjà utilisé

**Erreur :** `port is already allocated` ou `address already in use`

**Solution :**
1. Trouve quel processus utilise le port :
   ```bash
   # Sur Windows
   netstat -ano | findstr :9200
   
   # Sur Linux/Mac
   lsof -i :9200
   ```
2. Arrête le processus ou change le port dans `docker-compose.yml`

---

### Problème : Toots JSON invalides

**Erreur dans `validate_pipeline.py` :** `Champs manquants`

**Solution :**
1. Vérifie la version de Mastodon.py utilisée
2. Regarde les logs pour voir quels champs manquent
3. Vérifie que l'instance Mastodon fonctionne correctement

### Performance

- Redis peut stocker des millions de toots en mémoire
- Si la queue devient trop grande, le Membre 2 doit traiter plus rapidement
- Surveillance recommandée : `docker exec -it redis redis-cli LLEN mastodon_queue`

### Limites Mastodon API

- **Mastodon n'a pas de limites de rate strictes** (contrairement à Reddit/Twitter)
- Mastodon.py gère automatiquement les reconnexions WebSocket
- Ne pas ouvrir plusieurs instances de `mastodon_stream.py` en même temps avec le même token
