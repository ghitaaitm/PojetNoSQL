# ================================================
# FICHIER VALIDATE_PIPELINE.PY
# ================================================
# Ce script valide que le pipeline fonctionne correctement
# Il vérifie :
# 1. La connexion à Redis
# 2. La taille de la queue
# 3. Le format des JSON dans la queue
# 4. Génère un rapport avec 10 tweets collectés
from dotenv import load_dotenv
import os
import json
import redis
from datetime import datetime
from loguru import logger
import sys

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)

# ================================================
# FONCTION DE VALIDATION
# ================================================
def validate_pipeline():
    """
    Fonction principale de validation du pipeline
    Vérifie que tout fonctionne correctement
    """
    logger.info("=" * 60)
    logger.info("VALIDATION DU PIPELINE D'INGESTION")
    logger.info("=" * 60)
    
    load_dotenv()
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    queue_name = os.getenv('REDIS_QUEUE_NAME', 'mastodon_queue')
    
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logger.info("✓ Connexion à Redis réussie")
    except Exception as e:
        logger.error(f"✗ Erreur de connexion à Redis : {e}")
        return False
    
    try:
        queue_size = redis_client.llen(queue_name)
        logger.info(f"✓ Taille de la queue '{queue_name}' : {queue_size} posts")
        
        if queue_size == 0:
            logger.warning("⚠ La queue est vide ! Lance mastodon_stream.py pour collecter des toots.")
            return False
    except Exception as e:
        logger.error(f"✗ Erreur lors de la vérification de la queue : {e}")
        return False
    
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION DU FORMAT JSON")
    logger.info("=" * 60)
    
    posts_valid = 0
    posts_invalides = 0
    posts_exemples = []
    
    # On récupère les 10 premiers posts sans les supprimer (LRANGE au lieu de LPOP)
    for i in range(min(10, queue_size)):
        try:
            post_json_string = redis_client.lindex(queue_name, i)
            
            if not post_json_string:
                continue

            post_data = json.loads(post_json_string)
            
            # Vérification des champs obligatoires
            # On accepte soit tweet_id, post_id ou toot_id (compatibilité)
            post_id = post_data.get('post_id') or post_data.get('tweet_id') or post_data.get('toot_id')
            champs_obligatoires = ['text', 'author_id', 'created_at']
            champs_manquants = [champ for champ in champs_obligatoires if champ not in post_data]
            
            if champs_manquants or not post_id:
                missing = champs_manquants + (['post_id/tweet_id'] if not post_id else [])
                logger.warning(f"Post {i+1} : Champs manquants : {missing}")
                posts_invalides += 1
            else:
                posts_valid += 1
                
                # On garde les 10 premiers posts valides pour le rapport
                if len(posts_exemples) < 10:
                    posts_exemples.append(post_data)
                
                post_id_display = post_data.get('post_id') or post_data.get('tweet_id') or post_data.get('toot_id', 'N/A')
                logger.debug(f"Post/Toot {i+1} : ✓ Format valide | ID: {str(post_id_display)[:20]}...")
                
        except json.JSONDecodeError as e:
            logger.error(f"Post {i+1} : ✗ JSON invalide : {e}")
            posts_invalides += 1
        except Exception as e:
            logger.error(f"Post {i+1} : ✗ Erreur : {e}")
            posts_invalides += 1
    
    # Affichage des résultats
    logger.info("\n" + "=" * 60)
    logger.info("RÉSULTATS DE LA VALIDATION")
    logger.info("=" * 60)
    logger.info(f"Posts valides : {posts_valid}")
    logger.info(f"Posts invalides : {posts_invalides}")
    if posts_valid + posts_invalides > 0:
        logger.info(f"Taux de succès : {(posts_valid/(posts_valid+posts_invalides)*100):.1f}%")
    
    # Génération du rapport
    rapport_path = "rapport_validation.md"
    logger.info(f"\nGénération du rapport : {rapport_path}")
    
    with open(rapport_path, 'w', encoding='utf-8') as f:
        f.write("# RAPPORT DE VALIDATION - PIPELINE D'INGESTION\n\n")
        f.write(f"**Date :** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Auteur :** Membre 1\n\n")
        f.write("---\n\n")
        
        f.write("## 1. ÉTAT DE LA FILE D'ATTENTE REDIS\n\n")
        f.write(f"- **Nom de la queue :** `{queue_name}`\n")
        f.write(f"- **Taille actuelle :** {queue_size} posts\n")
        f.write(f"- **Posts valides :** {posts_valid}\n")
        f.write(f"- **Posts invalides :** {posts_invalides}\n")
        if posts_valid + posts_invalides > 0:
            f.write(f"- **Taux de succès :** {(posts_valid/(posts_valid+posts_invalides)*100):.1f}%\n\n")
        else:
            f.write("- **Taux de succès :** N/A\n\n")
        
        f.write("## 2. EXEMPLES DE POSTS/TOOTS COLLECTÉS\n\n")
        
        for idx, post in enumerate(posts_exemples, 1):
            f.write(f"### Post {idx}\n\n")
            f.write("```json\n")
            f.write(json.dumps(post, indent=2, ensure_ascii=False))
            f.write("\n```\n\n")
            f.write("---\n\n")
        
        f.write("## 3. CONCLUSION\n\n")
        if posts_valid > 0 and posts_invalides == 0:
            f.write("✅ **PIPELINE D'INGESTION OK**\n\n")
            f.write("Le pipeline fonctionne correctement. Les toots Mastodon sont collectés,\n")
            f.write("formatés correctement et stockés dans Redis.\n")
        elif posts_valid > 0:
            f.write("⚠️ **PIPELINE PARTIELLEMENT FONCTIONNEL**\n\n")
            f.write("Le pipeline fonctionne mais certains posts ont un format invalide.\n")
        else:
            f.write("❌ **PIPELINE NON FONCTIONNEL**\n\n")
            f.write("Aucun post valide trouvé dans la queue.\n")
    
    logger.info("✓ Rapport généré avec succès")
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION TERMINÉE")
    logger.info("=" * 60)
    
    return posts_valid > 0


if __name__ == "__main__":
    success = validate_pipeline()
    sys.exit(0 if success else 1)

