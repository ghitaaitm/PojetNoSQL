# ================================================
# FICHIER MASTODON_STREAM.PY
# ================================================
# Ce script collecte des posts Mastodon (toots) en temps réel
# et les envoie dans une file d'attente Redis
# 
# Mastodon API est GRATUITE et supporte le streaming temps réel !
# Parfait pour un projet académique
# ================================================
from dotenv import load_dotenv
import os
import json
import time
import sys
from mastodon import Mastodon, StreamListener
import redis
from datetime import datetime
from loguru import logger

# ================================================
# CONFIGURATION DES LOGS
# ================================================
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"  # Affiche INFO et plus sur la console
)
logger.add(
    "logs/mastodon_stream.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"  # Log DEBUG dans le fichier pour voir les détails
)


# ================================================
# CLASSE STREAMING LISTENER PERSONNALISÉE
# ================================================
class MastodonStreamListener(StreamListener):
    """
    Cette classe hérite de StreamListener de Mastodon.py
    Elle permet de redéfinir les méthodes appelées lors de la réception d'un toot
    """
    
    def __init__(self, redis_client, queue_name, hashtags_to_follow=None):
        """
        Constructeur de la classe
        
        Args:
            redis_client: Client Redis pour envoyer les toots
            queue_name: Nom de la queue Redis
            hashtags_to_follow: Liste des hashtags à suivre (sans le #). Si None, tous les toots sont collectés
        """
        self.redis_client = redis_client
        self.queue_name = queue_name
        self.hashtags_to_follow = hashtags_to_follow or []  # Liste des hashtags (sans le #)
        
        # Compteurs pour le monitoring
        self.toot_count = 0
        self.success_count = 0
        self.error_count = 0
        self.filtered_count = 0  # Toots filtrés (qui ne contiennent pas les hashtags)
        
        logger.info("Stream listener Mastodon initialisé avec succès")
        if self.hashtags_to_follow:
            logger.info(f"Hashtags suivis : {', '.join(['#' + h for h in self.hashtags_to_follow])}")
    
    def on_update(self, status):
        """
        Cette méthode est appelée automatiquement par Mastodon.py
        à chaque fois qu'on reçoit un nouveau toot
        
        Args:
            status: Dictionnaire contenant les données du toot
        """
        try:
            self.toot_count += 1
            
            # Log tous les 10 toots pour ne pas spammer
            if self.toot_count % 10 == 0:
                filtered_info = f" | Filtrés : {self.filtered_count}" if self.hashtags_to_follow else ""
                logger.info(f"Toots reçus : {self.toot_count} | Envoyés avec succès : {self.success_count} | Erreurs : {self.error_count}{filtered_info}")
            
            # ============================================
            # EXTRACTION DES DONNÉES DU TOOT
            # ============================================
            # On extrait les champs nécessaires pour le projet
            # ============================================
            
            # ID unique du toot
            toot_id = status.get('id', '')
            
            # Contenu du toot (text HTML, on nettoie les balises HTML)
            content = status.get('content', '')
            # On nettoie les balises HTML simples (basique)
            import re
            text = re.sub('<[^<]+?>', '', content)  # Supprime les balises HTML
            # On nettoie aussi les entités HTML (comme &nbsp;)
            text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            
            # Titre (Mastodon n'a pas de titre, on utilise les premiers mots)
            title = text[:100] + "..." if len(text) > 100 else text
            
            # Auteur du toot
            account = status.get('account', {})
            author_id = account.get('acct', '') if account else None  # acct = username@instance
            author_username = account.get('username', '') if account else None
            
            # Date de création (format ISO 8601)
            created_at = status.get('created_at', '')
            if created_at:
                # Convertir en format ISO si nécessaire
                if isinstance(created_at, str):
                    created_at = created_at
                else:
                    created_at = created_at.isoformat() + "Z"
            
            # Langue du toot
            lang = status.get('language', 'unknown')
            
            # Instance Mastodon
            uri = status.get('uri', '')
            instance = uri.split('/')[2] if '/' in uri else 'unknown'  # Extrait l'instance de l'URI
            
            # URL du toot
            url = status.get('url', uri)
            
            # Score (Mastodon a des favourites et des reblogs)
            favourites_count = status.get('favourites_count', 0)
            reblogs_count = status.get('reblogs_count', 0)
            replies_count = status.get('replies_count', 0)
            score = favourites_count + reblogs_count
            
            # Tags/hashtags
            # Dans Mastodon, les tags sont dans status['tags'] qui est une liste de dictionnaires
            # Chaque tag a la structure : {'name': 'hashtag', 'url': '...'}
            tags = status.get('tags', [])
            hashtags = []
            if tags:
                # Les tags peuvent être des dictionnaires ou des strings
                for tag in tags:
                    if isinstance(tag, dict):
                        # Format standard : {'name': 'hashtag', ...}
                        tag_name = tag.get('name', '')
                    elif isinstance(tag, str):
                        # Format alternatif : string direct
                        tag_name = tag
                    else:
                        continue
                    
                    if tag_name:
                        # On enlève le # au début s'il y en a un
                        tag_name = tag_name.lstrip('#')
                        hashtags.append(tag_name)
            
            # TOUJOURS extraire les hashtags depuis le texte/contenu HTML aussi
            # (Même si les tags Mastodon existent, on veut tous les hashtags du texte)
            # On cherche les mots précédés de # dans le contenu HTML (avant nettoyage)
            # Format : #hashtag ou #Hashtag (insensible à la casse)
            hashtag_pattern = r'#([a-zA-Z0-9_]+)'
            found_hashtags_html = re.findall(hashtag_pattern, content, re.IGNORECASE)
            found_hashtags_text = re.findall(hashtag_pattern, text, re.IGNORECASE)
            # Combine les hashtags trouvés dans le texte avec ceux des tags Mastodon
            all_found_hashtags = list(set(found_hashtags_html + found_hashtags_text))
            # Convertir en minuscules et enlever les doublons
            hashtags_from_text = [h.lower() for h in all_found_hashtags]
            # Combiner avec les hashtags des tags Mastodon (en minuscules aussi)
            hashtags_existing_lower = [h.lower() for h in hashtags]
            # Fusionner les deux listes et enlever les doublons
            hashtags = list(set(hashtags_existing_lower + hashtags_from_text))
            
            # ============================================
            # FILTRAGE PAR HASHTAGS (si configuré)
            # ============================================
            # Si on a configuré des hashtags à suivre, on filtre les toots
            # On ne garde que les toots qui contiennent au moins un des hashtags souhaités
            # ============================================
            if self.hashtags_to_follow:
                # On vérifie si le toot contient au moins un des hashtags souhaités
                # Les hashtags sont comparés en minuscules pour être insensibles à la casse
                hashtags_lower = [h.lower() for h in hashtags]
                hashtags_to_follow_lower = [h.lower() for h in self.hashtags_to_follow]
                
                # On vérifie aussi dans le texte du toot (au cas où le hashtag n'est pas dans les tags)
                # IMPORTANT : On vérifie aussi dans le contenu HTML original avant nettoyage
                content_lower = content.lower()  # Contenu HTML original
                text_lower = text.lower()  # Texte nettoyé
                
                # Vérification : soit dans les tags, soit dans le texte (avec ou sans #)
                # IMPORTANT : Utilise des word boundaries pour éviter les faux positifs
                # (ex: "IA" ne doit pas matcher dans "pneumonia")
                import re
                contains_hashtag = False
                for tag in hashtags_to_follow_lower:
                    # 1. Vérifie dans les tags Mastodon extraits (le plus fiable)
                    if tag in hashtags_lower:
                        contains_hashtag = True
                        break
                    
                    # 2. Vérifie les hashtags formatés avec # dans le contenu HTML ou texte
                    # Format : #hashtag (avec le #)
                    # On accepte avec ou sans word boundary pour les hashtags avec #
                    hashtag_pattern_with_hash = r'#' + re.escape(tag) + r'(?:\b|$)'
                    if re.search(hashtag_pattern_with_hash, content_lower) or re.search(hashtag_pattern_with_hash, text_lower):
                        contains_hashtag = True
                        break
                    
                    # 3. Vérifie le mot comme mot entier (word boundary) dans le texte
                    # Format : mot complet (pas comme partie d'un autre mot)
                    # Ex: "python" matche dans "j'aime python" mais pas dans "pythonic"
                    # Pour des hashtags courts (2-3 caractères), on est plus permissif
                    if len(tag) <= 3:
                        # Pour les tags courts (IA, AI), on cherche juste le mot (mais pas dans un autre mot)
                        # Ex: "IA" matche dans "j'aime l'IA" mais pas dans "pneumonia"
                        short_tag_pattern = r'\b' + re.escape(tag) + r'(?:\s|$|[^\w])'
                        if re.search(short_tag_pattern, text_lower) or re.search(short_tag_pattern, content_lower):
                            contains_hashtag = True
                            break
                    else:
                        # Pour les tags longs (python, Morocco), on utilise word boundaries strictes
                        word_pattern = r'\b' + re.escape(tag) + r'\b'
                        if re.search(word_pattern, text_lower) or re.search(word_pattern, content_lower):
                            contains_hashtag = True
                            break
                
                # Debug : log les premiers toots filtrés pour voir pourquoi
                if not contains_hashtag:
                    self.filtered_count += 1
                    # Log de debug pour les 3 premiers toots filtrés (dans le fichier de log)
                    if self.filtered_count <= 3:
                        logger.debug(f"Toot filtré #{self.filtered_count} - ID: {toot_id}")
                        logger.debug(f"  Hashtags trouvés dans les tags : {hashtags}")
                        logger.debug(f"  Hashtags recherchés : {self.hashtags_to_follow}")
                        logger.debug(f"  Texte (150 premiers chars) : {text[:150]}")
                        logger.debug(f"  Contenu HTML (150 premiers chars) : {content[:150]}")
                    # On continue sans envoyer ce toot dans Redis
                    return  # On sort de la fonction sans traiter ce toot
                else:
                    # Log quand un toot correspond (pour debug)
                    if self.success_count < 3:
                        logger.info(f"✓ Toot correspond trouvé #{self.success_count + 1} - Hashtags : {hashtags}")
            
            # ============================================
            # CRÉATION DU JSON NORMALISÉ
            # ============================================
            # Format similaire à Reddit/Twitter pour faciliter l'intégration
            # ============================================
            toot_json = {
                "toot_id": str(toot_id),  # Équivalent de tweet_id/post_id
                "tweet_id": str(toot_id),  # Garde la compatibilité avec validate_pipeline.py
                "post_id": str(toot_id),   # Garde la compatibilité
                "text": text,
                "title": title,  # Premiers mots du toot
                "author_id": author_id,  # username@instance
                "author_username": author_username,
                "created_at": created_at,
                "lang": lang,
                "hashtags": hashtags,
                "instance": instance,  # Spécifique à Mastodon
                "favourites_count": favourites_count,  # Spécifique à Mastodon
                "reblogs_count": reblogs_count,  # Spécifique à Mastodon
                "replies_count": replies_count,  # Spécifique à Mastodon
                "score": score,  # favourites + reblogs
                "url": url
            }
            
            # ============================================
            # ENVOI DANS REDIS VIA RPUSH
            # ============================================
            # Conversion en JSON string
            json_string = json.dumps(toot_json, ensure_ascii=False)
            
            # Tentative d'envoi dans Redis avec retry automatique
            max_retries = 3
            retry_delay = 1
            
            for attempt in range(max_retries):
                try:
                    # Envoi du toot dans la queue Redis
                    self.redis_client.rpush(self.queue_name, json_string)
                    
                    # Succès !
                    self.success_count += 1
                    
                    # Log de succès (seulement pour les premiers toots)
                    if self.success_count <= 5 or attempt > 0:
                        logger.debug(f"Toot envoyé dans Redis : {toot_id} | Instance: {instance} | Queue: {self.queue_name}")
                    
                    break  # On sort de la boucle de retry
                    
                except redis.ConnectionError as e:
                    self.error_count += 1
                    logger.warning(f"Erreur de connexion Redis (tentative {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))  # Délai progressif
                    else:
                        logger.error(f"Impossible d'envoyer le toot {toot_id} après {max_retries} tentatives")
                        
                except redis.RedisError as e:
                    self.error_count += 1
                    logger.error(f"Erreur Redis lors de l'envoi du toot {toot_id}: {e}")
                    break
                    
                except Exception as e:
                    self.error_count += 1
                    logger.error(f"Erreur inattendue lors de l'envoi du toot {toot_id}: {e}")
                    break
            
        except Exception as e:
            # Erreur générale dans le traitement du toot
            self.error_count += 1
            logger.error(f"Erreur lors du traitement d'un toot : {e}")
            logger.debug(f"Détails du toot problématique : {status.get('id', 'N/A')}")
    
    def on_notification(self, notification):
        """
        Cette méthode est appelée pour les notifications (non utilisé pour la collecte)
        """
        pass  # On ignore les notifications
    
    def on_delete(self, status_id):
        """
        Cette méthode est appelée quand un toot est supprimé
        """
        logger.debug(f"Toot supprimé : {status_id}")
        # On ne fait rien, on continue


# ================================================
# FONCTION PRINCIPALE
# ================================================
def main():
    """
    Fonction principale du script
    C'est ici que tout démarre
    """
    logger.info("=" * 60)
    logger.info("DÉMARRAGE DU STREAMING MASTODON")
    logger.info("=" * 60)
    
    # ============================================
    # CHARGEMENT DES VARIABLES D'ENVIRONNEMENT
    # ============================================
    load_dotenv()
    
    # Récupération des credentials Mastodon
    instance_url = os.getenv('MASTODON_INSTANCE_URL')
    access_token = os.getenv('MASTODON_ACCESS_TOKEN')
    
    if not instance_url or instance_url == 'INSTANCE_URL_ICI':
        logger.error("ERREUR : MASTODON_INSTANCE_URL non configuré dans le fichier .env")
        logger.error("1. Copie env.example en .env")
        logger.error("2. Choisis une instance Mastodon (ex: https://mastodon.social)")
        logger.error("3. Crée une application et récupère l'access token")
        logger.error("4. Ajoute l'instance URL et l'access token dans .env")
        sys.exit(1)
    
    if not access_token or access_token == 'ACCESS_TOKEN_ICI':
        logger.error("ERREUR : MASTODON_ACCESS_TOKEN non configuré dans le fichier .env")
        logger.error("Pour obtenir un access token:")
        logger.error("1. Va sur ton instance Mastodon (ex: https://mastodon.social)")
        logger.error("2. Va dans Préférences > Développement > Nouvelles applications")
        logger.error("3. Crée une application avec les permissions 'read'")
        logger.error("4. Copie l'access token généré")
        sys.exit(1)
    
    # Récupération de la configuration Redis
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    queue_name = os.getenv('REDIS_QUEUE_NAME', 'mastodon_queue')
    
    logger.info(f"Configuration chargée : Queue={queue_name}, Redis={redis_url}")
    logger.info(f"Instance Mastodon : {instance_url}")
    
    # ============================================
    # CONNEXION À MASTODON
    # ============================================
    try:
        # Création du client Mastodon avec l'instance et le token
        mastodon = Mastodon(
            access_token=access_token,
            api_base_url=instance_url
        )
        
        # Test de connexion : on vérifie que l'utilisateur est authentifié
        account = mastodon.account_verify_credentials()
        logger.info(f"Connexion à Mastodon réussie ✓")
        logger.info(f"Compte : @{account.get('username', 'N/A')}@{instance_url.replace('https://', '')}")
        
    except Exception as e:
        logger.error(f"ERREUR : Impossible de se connecter à Mastodon : {e}")
        logger.error("Vérifie ton instance URL et ton access token dans le fichier .env")
        sys.exit(1)
    
    # ============================================
    # CONNEXION À REDIS
    # ============================================
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logger.info("Connexion à Redis réussie ✓")
        
    except redis.ConnectionError:
        logger.error("ERREUR : Impossible de se connecter à Redis")
        logger.error("Vérifie que Redis est démarré : docker compose up -d")
        sys.exit(1)
    
    # ============================================
    # CONFIGURATION DES HASHTAGS À SUIVRE
    # ============================================
    # Liste des hashtags à suivre (sans le #)
    # Tu peux modifier cette liste selon tes besoins
    # ============================================
    hashtags_to_follow = [
        # Hashtags du projet (spécifiques)
        'Maroc', 'Morocco',        
        'IA', 'AI', 'IntelligenceArtificielle',  
        'python', 'Python',        
        'NoSQL', 'nosql',          
        'MachineLearning', 'MachineLearning',
        # Hashtags généraux populaires (pour avoir plus de données)
        'tech', 'technology',      
        'coding', 'programming',   
        'opensource',              
        'dev', 'development',      
    ]
    
    logger.info(f"Hashtags à suivre : {', '.join(['#' + h for h in hashtags_to_follow])}")
    
    # ============================================
    # CRÉATION DU STREAM LISTENER
    # ============================================
    listener = MastodonStreamListener(
        redis_client=redis_client,
        queue_name=queue_name,
        hashtags_to_follow=hashtags_to_follow  # On passe la liste des hashtags
    )
    
    # ============================================
    # DÉMARRAGE DU STREAMING
    # ============================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("STREAMING ACTIF - Écoute des toots Mastodon en temps réel...")
    logger.info("Appuie sur Ctrl+C pour arrêter")
    logger.info("=" * 60)
    logger.info("")
    if hashtags_to_follow:
        logger.info(f"📡 Streaming filtré par hashtags : {', '.join(['#' + h for h in hashtags_to_follow])}")
    else:
        logger.info("📡 Streaming depuis le timeline public de l'instance...")
    
    try:
        # Démarrage du streaming temps réel
        # stream_public() stream le timeline public de l'instance en temps réel
        # Le filtre par hashtags est fait dans le listener (on_update)
        mastodon.stream_public(listener)
        
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Arrêt demandé par l'utilisateur (Ctrl+C)")
        
    except Exception as e:
        logger.error(f"Erreur fatale : {e}")
        
    finally:
        logger.info("")
        logger.info("=" * 60)
        logger.info("RÉSUMÉ DE LA COLLECTE")
        logger.info("=" * 60)
        logger.info(f"Toots reçus : {listener.toot_count}")
        if listener.hashtags_to_follow:
            logger.info(f"Toots filtrés (sans hashtags) : {listener.filtered_count}")
        logger.info(f"Toots envoyés avec succès : {listener.success_count}")
        logger.info(f"Erreurs : {listener.error_count}")
        logger.info("")
        logger.info("Arrêt du streaming Mastodon")


# ================================================
# POINT D'ENTRÉE DU SCRIPT
# ================================================
if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    main()

