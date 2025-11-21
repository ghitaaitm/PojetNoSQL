# INFORMATIONS POUR MEMBRE 2

**Données fournies par le Membre 1**

---

## PRÉREQUIS

**Tu dois lancer Docker sur ta machine pour accéder à Redis :**

```bash
# Depuis le dossier du projet
docker compose up -d
```

Cela lance Redis, Elasticsearch et Kibana. Redis est nécessaire pour consommer les données.

**IMPORTANT :** Chaque membre a sa propre machine avec son propre Redis local. 

**On utilise le même fichier `.env`** (credentials Mastodon partagés).

**Pour avoir des données à analyser :**

Tu peux collecter les données toi-même :
- Utiliser le fichier `.env` partagé (les credentials Mastodon sont déjà configurés)
- Lancer `python mastodon_stream.py` pour collecter des toots dans ta propre queue Redis
- Puis consommer les données avec ton script d'analyse

---
## COMMENT FAIRE, EN BREF

### Étape 1 : Lancer Docker (si ce n'est pas déjà fait)

**Sur ta machine**, lance Docker à partir du dossier du projet:
```bash
docker compose up -d
```

Cela lance Redis, Elasticsearch et Kibana.

**Note :** Les dossiers `data/elasticsearch`, `data/kibana` et `data/redis` seront créés automatiquement par Docker si ils n'existent pas. Tu n'as pas besoin de les créer manuellement.

**Vérifie que les conteneurs tournent :**
```bash
docker ps
# Doit afficher les conteneurs elasticsearch, kibana, redis
```

### Étape 2 : Vérifier que Redis, Elasticsearch et Kibana sont actifs

**Vérifier Redis :**
```bash
docker exec -it redis redis-cli PING
# Doit répondre : PONG
```

**Vérifier Elasticsearch :**
```bash
# Méthode 1 : Vérifier via le navigateur
# Ouvre http://localhost:9200 dans ton navigateur
# Tu devrais voir du JSON avec des infos sur Elasticsearch

# Méthode 2 : Vérifier via curl (si installé)
curl http://localhost:9200
# Doit retourner du JSON avec des infos Elasticsearch
```

**Vérifier Kibana :**
```bash
# Méthode 1 : Vérifier via le navigateur
# Ouvre http://localhost:5601 dans ton navigateur
# Tu devrais voir l'interface de Kibana (peut prendre 30-60 secondes au démarrage)

# Méthode 2 : Vérifier via curl (si installé)
curl http://localhost:5601
# Doit retourner du HTML (page de Kibana)
```

Si Redis, Elasticsearch ou Kibana ne fonctionne pas :
- Vérifie que Docker est bien lancé : `docker ps`
- Redémarre les services : `docker compose restart`
- Vérifie les logs : 
  - `docker compose logs elasticsearch`
  - `docker compose logs redis`
  - `docker compose logs kibana`

### Étape 3 : Vérifier la taille de la queue

```bash
docker exec -it redis redis-cli LLEN mastodon_queue
# Retourne le nombre de toots en attente
```

Si la queue est vide (0), tu dois collecter des données toi-même :
- Crée le fichier `.env` partagé (déjà configuré)
- Lancer `python mastodon_stream.py` pour collecter des toots

laisse tourner quelques minutes (c'est lent à cause du filtre de hashtags)

---

## ACCÈS À LA QUEUE REDIS

### Nom de la queue
```
mastodon_queue
```

### Connexion Redis
```
redis://localhost:6379
```

Redis est déjà configuré dans Docker (port 6379).

---

## FORMAT DES DONNÉES

Chaque toot est stocké dans Redis comme une chaîne JSON.

### Structure JSON d'un toot

```json
{
  "toot_id": "115589646295381510",
  "tweet_id": "115589646295381510",
  "post_id": "115589646295381510",
  "text": "Contenu du toot...",
  "title": "Titre (premiers 100 caractères)...",
  "author_id": "username@instance.mastodon",
  "author_username": "username",
  "created_at": "2025-11-21T20:47:10.629000+00:00Z",
  "lang": "en",
  "hashtags": ["python", "tech", "coding"],
  "instance": "mastodon.social",
  "favourites_count": 0,
  "reblogs_count": 0,
  "replies_count": 0,
  "score": 0,
  "url": "https://mastodon.social/@username/115589646295381510"
}
```

### Champs disponibles

- `toot_id` : ID unique du toot (string)
- `tweet_id` : Alias de toot_id (compatibilité)
- `post_id` : Alias de toot_id (compatibilité)
- `text` : Contenu textuel du toot (string)
- `title` : Titre extrait (premiers 100 caractères du texte)
- `author_id` : Identifiant complet de l'auteur (format: username@instance)
- `author_username` : Nom d'utilisateur seulement
- `created_at` : Date de création (format ISO 8601 avec Z)
- `lang` : Langue du toot (code ISO, ex: "en", "fr", "pt")
- `hashtags` : Liste des hashtags extraits (array de strings)
- `instance` : Instance Mastodon d'origine (string)
- `favourites_count` : Nombre de favoris (integer)
- `reblogs_count` : Nombre de reblogs (integer)
- `replies_count` : Nombre de réponses (integer)
- `score` : Score calculé (favourites_count + reblogs_count)
- `url` : URL complète du toot

---

## COMMENT CONSOMMER LES DONNÉES

### Méthode 1 : Redis CLI (test rapide)

```bash
# Voir la taille de la queue
docker exec -it redis redis-cli LLEN mastodon_queue

# Consommer un toot (le supprime de la queue)
docker exec -it redis redis-cli LPOP mastodon_queue

# Voir un toot sans le supprimer
docker exec -it redis redis-cli LRANGE mastodon_queue 0 0
```

### Méthode 2 : Python (production)

```python
import redis
import json

# Connexion à Redis
redis_client = redis.from_url('redis://localhost:6379', decode_responses=True)
queue_name = 'mastodon_queue'

# Consommer un toot
toot_json = redis_client.lpop(queue_name)
if toot_json:
    toot = json.loads(toot_json)
    print(toot['text'])
    # Faire l'analyse ici...
```

---


## NOTES IMPORTANTES

1. **Format des dates** : `created_at` est au format ISO 8601 avec timezone UTC (se termine par Z)

2. **Hashtags** : La liste `hashtags` peut être vide `[]` si aucun hashtag n'est trouvé dans le toot

3. **IDs multiples** : `toot_id`, `tweet_id`, `post_id` contiennent la même valeur (compatibilité avec différentes nomenclatures)

4. **Queue FIFO** : Les toots sont stockés dans l'ordre d'arrivée (FIFO - First In First Out)

5. **Consommation** : Utiliser `LPOP` pour consommer (supprime de la queue) ou `LRANGE` pour lire sans supprimer

---

## FICHIERS DE RÉFÉRENCE

- `validate_pipeline.py` : Script qui montre comment lire les données Redis
- `rapport_validation.md` : Exemples de toots collectés avec tous les champs
- `README.md` : Documentation complète du pipeline