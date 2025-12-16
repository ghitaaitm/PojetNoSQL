"""
Script de configuration rapide pour changer le mode de filtrage
VERSION SAFE - Préserve les credentials Mastodon existants
"""

import os
import sys
from pathlib import Path

def print_menu():
    """Afficher le menu de sélection"""
    print("\n" + "=" * 70)
    print("🔧 CONFIGURATION DU MODE DE FILTRAGE - MASTODON ABSA V2")
    print("=" * 70)
    print("\nChoisissez un mode de filtrage :\n")
    
    print("1. STRICT")
    print("   • Longueur minimum : 3 caractères")
    print("   • POS autorisés : NOUN, PROPN, ADJ")
    print("   • Stopwords : Liste étendue")
    print("   • Répétitions max : 6")
    print("   • Taux de filtrage : ~85-90%")
    print("   • Usage : Qualité maximale, analyse précise\n")
    
    print("2. BALANCED (recommandé)")
    print("   • Longueur minimum : 2 caractères")
    print("   • POS autorisés : NOUN, PROPN, ADJ, VERB")
    print("   • Stopwords : Liste minimale")
    print("   • Répétitions max : 10")
    print("   • Taux de filtrage : ~70-80%")
    print("   • Usage : Équilibre qualité/volume\n")
    
    print("3. PERMISSIVE")
    print("   • Longueur minimum : 2 caractères")
    print("   • POS autorisés : NOUN, PROPN, ADJ, VERB, ADV")
    print("   • Stopwords : Liste minimale")
    print("   • Répétitions max : 15")
    print("   • Taux de filtrage : ~60-70%")
    print("   • Usage : Volume maximal, exploration\n")
    
    print("=" * 70)


def load_existing_env():
    """Charger le .env existant et parser les variables"""
    env_vars = {}
    
    if not Path('.env').exists():
        return env_vars
    
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Ignorer les commentaires et lignes vides
            if not line or line.startswith('#'):
                continue
            # Parser les variables
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars


def create_env_file(mode, existing_vars):
    """Créer/Mettre à jour le fichier .env en préservant les credentials"""
    
    # Variables par défaut
    defaults = {
        'REDIS_URL': 'redis://localhost:6379',
        'QUEUE_NAME': 'mastodon_queue',
        'ES_HOST': 'http://localhost:9200',
        'ES_INDEX_PREFIX': 'mastodon-trends',
    }
    
    # Merge : garder les valeurs existantes, ajouter les nouvelles
    final_vars = {**defaults, **existing_vars}
    
    # Mettre à jour le mode de filtrage
    final_vars['FILTER_MODE'] = mode
    
    # Construire le contenu du fichier
    env_content = f"""# Configuration MASTODON ABSA V2
# Généré automatiquement - Ne pas éditer manuellement

# Mode de filtrage (strict, balanced, permissive)
FILTER_MODE={final_vars.get('FILTER_MODE', mode)}

# Mastodon credentials
"""
    
    # Ajouter les credentials Mastodon s'ils existent
    if 'MASTODON_INSTANCE_URL' in final_vars:
        env_content += f"MASTODON_INSTANCE_URL={final_vars['MASTODON_INSTANCE_URL']}\n"
    else:
        env_content += "# MASTODON_INSTANCE_URL=https://mastodon.social\n"
    
    if 'MASTODON_ACCESS_TOKEN' in final_vars:
        env_content += f"MASTODON_ACCESS_TOKEN={final_vars['MASTODON_ACCESS_TOKEN']}\n"
    else:
        env_content += "# MASTODON_ACCESS_TOKEN=votre_token_ici\n"
    
    env_content += f"""
# Redis configuration
REDIS_URL={final_vars['REDIS_URL']}
QUEUE_NAME={final_vars['QUEUE_NAME']}

# Elasticsearch configuration
ES_HOST={final_vars['ES_HOST']}
ES_INDEX_PREFIX={final_vars['ES_INDEX_PREFIX']}
"""
    
    # Sauvegarder l'ancien .env
    if Path('.env').exists():
        if Path('.env.backup').exists():
            os.remove('.env.backup')
        os.rename('.env', '.env.backup')
        print("✓ Ancien .env sauvegardé dans .env.backup")
    
    # Écrire le nouveau .env
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"✓ Fichier .env mis à jour avec mode : {mode.upper()}")
    
    # Vérifier si les credentials sont présents
    if 'MASTODON_INSTANCE_URL' not in final_vars or 'MASTODON_ACCESS_TOKEN' not in final_vars:
        print("\n⚠️  ATTENTION : Credentials Mastodon manquants dans .env")
        print("   Vous devez ajouter :")
        print("   - MASTODON_INSTANCE_URL=https://votre.instance")
        print("   - MASTODON_ACCESS_TOKEN=votre_token")
        return False
    else:
        print(f"✓ Credentials Mastodon préservés")
        print(f"  Instance : {final_vars['MASTODON_INSTANCE_URL']}")
        token_masked = final_vars['MASTODON_ACCESS_TOKEN'][:8] + "..." + final_vars['MASTODON_ACCESS_TOKEN'][-8:]
        print(f"  Token    : {token_masked}")
        return True


def create_startup_script(mode):
    """Créer un script de démarrage personnalisé"""
    if sys.platform == 'win32':
        # Script Windows
        script_name = f'start_pipeline_{mode}.bat'
        content = f"""@echo off
echo Starting Mastodon ABSA Pipeline - Mode: {mode.upper()}
set FILTER_MODE={mode}
python startup_realtime_v2.py
pause
"""
    else:
        # Script Unix
        script_name = f'start_pipeline_{mode}.sh'
        content = f"""#!/bin/bash
echo "Starting Mastodon ABSA Pipeline - Mode: {mode.upper()}"
export FILTER_MODE={mode}
python3 startup_realtime_v2.py
"""
    
    with open(script_name, 'w', encoding='utf-8') as f:
        f.write(content)
    
    if not sys.platform == 'win32':
        os.chmod(script_name, 0o755)
    
    print(f"✓ Script de démarrage créé : {script_name}")


def main():
    print_menu()
    
    choice = input("\nVotre choix (1-3) : ").strip()
    
    modes = {
        '1': 'strict',
        '2': 'balanced',
        '3': 'permissive'
    }
    
    if choice not in modes:
        print("\n✗ Choix invalide. Annulation.")
        sys.exit(1)
    
    mode = modes[choice]
    
    print(f"\n" + "=" * 70)
    print(f"Configuration du mode : {mode.upper()}")
    print("=" * 70)
    
    # Charger le .env existant
    print("\nChargement de la configuration existante...")
    existing_vars = load_existing_env()
    
    if existing_vars:
        print(f"✓ {len(existing_vars)} variables trouvées dans .env")
        if 'MASTODON_INSTANCE_URL' in existing_vars:
            print(f"  → Instance Mastodon : {existing_vars['MASTODON_INSTANCE_URL']}")
        if 'MASTODON_ACCESS_TOKEN' in existing_vars:
            print(f"  → Token Mastodon : ****** (préservé)")
    else:
        print("⚠️  Aucun .env existant trouvé")
    
    print()
    
    # Créer/mettre à jour le fichier .env
    credentials_ok = create_env_file(mode, existing_vars)
    
    # Créer le script de démarrage
    create_startup_script(mode)
    
    print("\n" + "=" * 70)
    print("✅ CONFIGURATION TERMINÉE")
    print("=" * 70)
    print(f"\nMode sélectionné : {mode.upper()}")
    
    if not credentials_ok:
        print("\n⚠️  ACTION REQUISE : Configurer les credentials Mastodon")
        print("\nÉditez le fichier .env et ajoutez :")
        print("  MASTODON_INSTANCE_URL=https://votre.instance.mastodon")
        print("  MASTODON_ACCESS_TOKEN=votre_token_d_acces")
        print("\nPuis relancez le pipeline.")
    else:
        print("\n✅ Configuration complète - Prêt à démarrer")
        print("\nPour démarrer le pipeline :")
        
        if sys.platform == 'win32':
            print(f"  → Double-cliquez sur : start_pipeline_{mode}.bat")
            print(f"  → Ou en ligne de commande : start_pipeline_{mode}.bat")
        else:
            print(f"  → En ligne de commande : ./start_pipeline_{mode}.sh")
        
        print("\nPour changer de mode plus tard :")
        print("  → Relancez ce script : python configure_filter_mode.py")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Configuration annulée.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Erreur : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)