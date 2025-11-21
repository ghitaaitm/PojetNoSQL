# ================================================
# SCRIPT POUR VIDER LA QUEUE REDIS
# ================================================
# Ce script vide la queue Redis pour repartir à zéro
# Utile quand on change les filtres (hashtags, etc.)
# ================================================
from dotenv import load_dotenv
import os
import redis
from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")

def clear_queue():
    """
    Vide la queue Redis
    """
    logger.info("=" * 60)
    logger.info("VIDAGE DE LA QUEUE REDIS")
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
        # On récupère la taille actuelle
        queue_size = redis_client.llen(queue_name)
        logger.info(f"Taille actuelle de la queue '{queue_name}' : {queue_size} toots")
        
        if queue_size == 0:
            logger.info("⚠ La queue est déjà vide !")
            return True
        
        # On vide la queue en supprimant tous les éléments
        # On utilise DEL pour supprimer toute la liste
        redis_client.delete(queue_name)
        
        # On vérifie que c'est bien vide
        new_size = redis_client.llen(queue_name)
        
        if new_size == 0:
            logger.info(f"✓ Queue vidée avec succès ! ({queue_size} toots supprimés)")
            return True
        else:
            logger.error(f"✗ Erreur : la queue contient encore {new_size} toots")
            return False
            
    except Exception as e:
        logger.error(f"✗ Erreur lors du vidage : {e}")
        return False

if __name__ == "__main__":
    success = clear_queue()
    sys.exit(0 if success else 1)