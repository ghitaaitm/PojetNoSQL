"""
Script de diagnostic - Vérifier la structure exacte des données
"""
import requests
import json

ES_URL = "http://localhost:9200"
INDEX_PATTERN = "mastodon-trends-*"

def check_mapping():
    """Vérifier le mapping Elasticsearch"""
    print("=" * 70)
    print("MAPPING ELASTICSEARCH")
    print("=" * 70)
    
    try:
        response = requests.get(f"{ES_URL}/{INDEX_PATTERN}/_mapping", timeout=5)
        data = response.json()
        
        # Premier index
        first_index = list(data.keys())[0]
        properties = data[first_index]['mappings']['properties']
        
        print(f"\nIndex: {first_index}")
        print("\nChamps disponibles:")
        for field_name, field_info in sorted(properties.items()):
            field_type = field_info.get('type', 'object')
            
            if field_type == 'object' and 'properties' in field_info:
                print(f"  • {field_name} (object):")
                for sub_field, sub_info in field_info['properties'].items():
                    sub_type = sub_info.get('type', 'unknown')
                    print(f"      - {field_name}.{sub_field}: {sub_type}")
            else:
                print(f"  • {field_name}: {field_type}")
        
        return properties
    except Exception as e:
        print(f"✗ Erreur: {e}")
        return None

def check_sample_docs():
    """Récupérer des documents exemples"""
    print("\n" + "=" * 70)
    print("DOCUMENTS EXEMPLES")
    print("=" * 70)
    
    try:
        response = requests.get(
            f"{ES_URL}/{INDEX_PATTERN}/_search",
            params={"size": 3},
            timeout=5
        )
        data = response.json()
        hits = data.get('hits', {}).get('hits', [])
        
        for i, hit in enumerate(hits, 1):
            doc = hit['_source']
            print(f"\n--- Document {i} ---")
            print(f"ID: {doc.get('id', 'N/A')}")
            print(f"Langue: {doc.get('language', 'N/A')}")
            print(f"Texte: {doc.get('text', '')[:80]}...")
            
            # Aspects
            aspects = doc.get('aspects')
            print(f"Aspects (type={type(aspects).__name__}): {aspects}")
            
            # Sentiment
            sentiment = doc.get('sentiment')
            print(f"Sentiment: {sentiment}")
            
            # Critical tone
            tone = doc.get('critical_tone')
            print(f"Tone: {tone}")
            
            # Métadonnées
            metadata = doc.get('metadata')
            print(f"Metadata: {metadata}")
            
            # Structure complète
            print("\nStructure JSON complète:")
            print(json.dumps(doc, indent=2, ensure_ascii=False)[:500])
    
    except Exception as e:
        print(f"✗ Erreur: {e}")

def check_aggregations():
    """Tester les aggregations sur chaque champ"""
    print("\n" + "=" * 70)
    print("TEST DES AGGREGATIONS")
    print("=" * 70)
    
    fields_to_test = [
        "aspects",
        "sentiment.label",
        "critical_tone.tone",
        "language"
    ]
    
    for field in fields_to_test:
        print(f"\n Testing: {field}")
        try:
            agg_query = {
                "size": 0,
                "aggs": {
                    "test": {
                        "terms": {
                            "field": field,
                            "size": 5
                        }
                    }
                }
            }
            
            response = requests.post(
                f"{ES_URL}/{INDEX_PATTERN}/_search",
                json=agg_query,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                buckets = data.get('aggregations', {}).get('test', {}).get('buckets', [])
                
                if buckets:
                    print(f"  ✓ {field} - FONCTIONNE")
                    for bucket in buckets[:3]:
                        print(f"     - {bucket['key']}: {bucket['doc_count']}")
                else:
                    print(f"  ⚠️  {field} - Aucune donnée")
            else:
                print(f"  ✗ {field} - Erreur {response.status_code}")
                error = response.json()
                if 'error' in error:
                    print(f"     Raison: {error['error'].get('type', 'unknown')}")
                    
        except Exception as e:
            print(f"  ✗ {field} - Exception: {e}")

def main():
    print("\n" + "=" * 70)
    print("🔍 DIAGNOSTIC COMPLET DES DONNÉES")
    print("=" * 70)
    
    # Vérifier mapping
    mapping = check_mapping()
    
    # Vérifier documents
    check_sample_docs()
    
    # Tester aggregations
    check_aggregations()
    
    print("\n" + "=" * 70)
    print("✅ DIAGNOSTIC TERMINÉ")
    print("=" * 70)
    print("\nAnalyse les résultats ci-dessus pour identifier le problème.")
    print("\nPoints à vérifier:")
    print("  1. Les champs 'aspects', 'sentiment.label', etc. existent-ils?")
    print("  2. Quel est leur type (keyword, text, object)?")
    print("  3. Les aggregations fonctionnent-elles?")
    print("=" * 70)

if __name__ == "__main__":
    main()
