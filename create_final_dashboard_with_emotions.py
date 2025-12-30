#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSA Kibana Dashboard - VERSION FINALE CORRIGÉE
Combine les meilleures parties des deux versions :
- Détection automatique des champs (version 1)
- Couleurs pastels harmonieuses (version 2)
- Métriques fonctionnelles corrigées
- Markdown enrichi
"""

import sys
import json
import time
import requests
from typing import Dict, Optional

ES_URL = "http://localhost:9200"
KIBANA_URL = "http://localhost:5601"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}

# PALETTE PASTELS
PASTEL_COLORS = {
    "primary": "#B4D7E8",      # Bleu pastel
    "secondary": "#F7C6D8",    # Rose pastel
    "success": "#C8E6C9",      # Vert pastel
    "warning": "#FFE0B2",      # Orange pastel
    "danger": "#FFCDD2",       # Rouge pastel
    "info": "#E1BEE7",         # Violet pastel
    "neutral": "#E8EAF6",      # Indigo pastel
    "joy": "#FFF9C4",          # Jaune pastel
    "sadness": "#B3E5FC",      # Cyan pastel
    "anger": "#FFCCBC",        # Corail pastel
    "fear": "#D1C4E9",         # Lavande pastel
    "surprise": "#F8BBD0",     # Pink pastel
    "love": "#FCE4EC",         # Rose très clair
    "disgust": "#DCEDC8"       # Lime pastel
}

# ========================================
# UTILITAIRES HTTP
# ========================================

def http_get(url, **kwargs):
    try:
        r = requests.get(url, timeout=kwargs.get("timeout", 10))
        return r
    except Exception as e:
        print(f"✗ GET {url}: {e}")
        return None

def http_post(url, payload=None, **kwargs):
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=kwargs.get("timeout", 15))
        return r
    except Exception as e:
        print(f"✗ POST {url}: {e}")
        return None

def http_delete(url, **kwargs):
    try:
        r = requests.delete(url, headers=HEADERS, timeout=kwargs.get("timeout", 10))
        return r
    except Exception as e:
        print(f"✗ DELETE {url}: {e}")
        return None

# ========================================
# VÉRIFICATIONS
# ========================================

def check_services():
    print("\n" + "="*80)
    print("🔍 VÉRIFICATION DES SERVICES")
    print("="*80)
    
    r = http_get(ES_URL, timeout=5)
    if not r or r.status_code != 200:
        print("✗ Elasticsearch inaccessible")
        return False
    print("✓ Elasticsearch OK")
    
    r = http_get(f"{KIBANA_URL}/api/status", timeout=5)
    if not r or r.status_code != 200:
        print("✗ Kibana inaccessible")
        return False
    print("✓ Kibana OK")
    
    return True

# ========================================
# DÉTECTION INDEX & MAPPING
# ========================================

def find_best_index(prefix="mastodon-trends"):
    url = f"{ES_URL}/_cat/indices/{prefix}*?format=json"
    r = http_get(url, timeout=8)
    
    if not r or r.status_code != 200:
        print("✗ Impossible de lister les indices")
        return None
    
    indices = r.json()
    if not indices:
        print("✗ Aucun index mastodon-trends* trouvé")
        return None
    
    indices.sort(key=lambda x: int(x.get("docs.count", 0)), reverse=True)
    best = indices[0].get("index")
    docs = int(indices[0].get("docs.count", 0))
    
    print(f"✓ Index sélectionné: {best} ({docs:,} docs)")
    return best

def analyze_mapping(index_name: str) -> Dict[str, str]:
    print("\n" + "="*80)
    print("🔍 ANALYSE DU MAPPING ELASTICSEARCH")
    print("="*80)
    
    url = f"{ES_URL}/{index_name}/_mapping"
    r = http_get(url, timeout=8)
    
    if not r or r.status_code != 200:
        print("✗ Impossible de récupérer le mapping")
        return None
    
    mapping = r.json()
    props = mapping.get(index_name, {}).get("mappings", {}).get("properties", {})
    
    fields = {}
    
    # ASPECTS
    aspects_info = props.get("aspects", {})
    aspects_type = aspects_info.get("type")
    
    if aspects_type == "keyword":
        fields["aspects"] = "aspects"
        print("✓ aspects: type=keyword → 'aspects'")
    elif aspects_type == "text":
        if "keyword" in aspects_info.get("fields", {}):
            fields["aspects"] = "aspects.keyword"
            print("✓ aspects: type=text + .keyword → 'aspects.keyword'")
        else:
            fields["aspects"] = "aspects"
            print("⚠ aspects: type=text SANS .keyword → 'aspects'")
    else:
        fields["aspects"] = "aspects.keyword"
        print(f"⚠ aspects: type={aspects_type} → 'aspects.keyword'")
    
    # HASHTAGS
    hashtags_info = props.get("metadata", {}).get("properties", {}).get("hashtags", {})
    hashtags_type = hashtags_info.get("type")
    
    if hashtags_type == "keyword":
        fields["hashtags"] = "metadata.hashtags"
        print("✓ metadata.hashtags: type=keyword → 'metadata.hashtags'")
    elif hashtags_type == "text":
        if "keyword" in hashtags_info.get("fields", {}):
            fields["hashtags"] = "metadata.hashtags.keyword"
            print("✓ metadata.hashtags: type=text + .keyword → 'metadata.hashtags.keyword'")
        else:
            fields["hashtags"] = "metadata.hashtags"
            print("⚠ metadata.hashtags: type=text SANS .keyword → 'metadata.hashtags'")
    else:
        fields["hashtags"] = "metadata.hashtags.keyword"
        print(f"⚠ metadata.hashtags: type={hashtags_type} → 'metadata.hashtags.keyword'")
    
    # SENTIMENT LABEL
    sentiment_label_info = props.get("sentiment", {}).get("properties", {}).get("label", {})
    sentiment_type = sentiment_label_info.get("type")
    
    if sentiment_type == "keyword":
        fields["sentiment_label"] = "sentiment.label"
        print("✓ sentiment.label: type=keyword → 'sentiment.label'")
    elif sentiment_type == "text":
        if "keyword" in sentiment_label_info.get("fields", {}):
            fields["sentiment_label"] = "sentiment.label.keyword"
            print("✓ sentiment.label: type=text + .keyword → 'sentiment.label.keyword'")
        else:
            fields["sentiment_label"] = "sentiment.label"
            print("⚠ sentiment.label: type=text SANS .keyword → 'sentiment.label'")
    else:
        fields["sentiment_label"] = "sentiment.label.keyword"
        print(f"⚠ sentiment.label: type={sentiment_type} → 'sentiment.label.keyword'")
    
    # EMOTIONS
    has_emotions_flat = "emotions_flat" in props
    emotions_info = props.get("emotions", {})
    
    if has_emotions_flat:
        fields["has_emotions_flat"] = True
        fields["emotions"] = "emotions_flat"
        print("✓ emotions_flat: EXISTE (keyword) → 'emotions_flat' ✅")
    else:
        fields["has_emotions_flat"] = False
        emo_type = emotions_info.get("type")
        
        if emo_type == "nested":
            fields["emotions"] = "emotions.emotion"
            print("⚠ emotions: type=nested → 'emotions.emotion'")
        elif emo_type == "keyword":
            fields["emotions"] = "emotions"
            print("✓ emotions: type=keyword → 'emotions'")
        elif emo_type == "object":
            if "emotion" in emotions_info.get("properties", {}):
                fields["emotions"] = "emotions.emotion"
                print("⚠ emotions: type=object avec .emotion → 'emotions.emotion'")
            else:
                fields["emotions"] = "emotions"
                print("⚠ emotions: type=object → 'emotions'")
        else:
            fields["emotions"] = "emotions"
            print(f"⚠ emotions: type={emo_type} → 'emotions'")
    
    print("\n📋 RÉSUMÉ DES CHAMPS:")
    for key, value in fields.items():
        if key != "has_emotions_flat":
            print(f"  • {key:20} → {value}")
    
    return fields

# ========================================
# DATA VIEW
# ========================================

def find_existing_data_view(prefix_title):
    r = http_get(f"{KIBANA_URL}/api/data_views", timeout=10)
    if not r or r.status_code != 200:
        return None
    
    dvs = r.json().get("data_view", [])
    for dv in dvs:
        title = dv.get("title", "")
        dv_id = dv.get("id")
        if prefix_title.lower() in title.lower():
            print(f"✓ Data View existant: {title}")
            return dv_id
    return None

def create_or_update_data_view(index_name, guess_id=None):
    data_view_payload = {
        "data_view": {
            "title": f"{index_name}*",
            "name": "Mastodon Trends ABSA",
            "timeFieldName": "created_at"
        },
        "override": True
    }
    
    if guess_id:
        url = f"{KIBANA_URL}/api/data_views/data_view/{guess_id}"
        r = http_post(url, payload=data_view_payload, timeout=12)
        if r and r.status_code in (200, 201):
            print(f"✓ Data View créé/mis à jour: {guess_id}")
            return guess_id
    
    r = http_post(f"{KIBANA_URL}/api/data_views/data_view", payload=data_view_payload, timeout=12)
    if r and r.status_code in (200, 201):
        dv = r.json().get("data_view", {})
        dv_id = dv.get("id")
        print(f"✓ Data View créé: {dv_id}")
        return dv_id
    
    print("✗ Échec Data View")
    return None

# ========================================
# CLEANUP
# ========================================

def deep_cleanup():
    deleted = 0
    
    r = http_get(f"{KIBANA_URL}/api/saved_objects/_find?type=visualization&per_page=1000", timeout=12)
    if r and r.status_code == 200:
        for obj in r.json().get("saved_objects", []):
            vid = obj.get("id")
            title = obj.get("attributes", {}).get("title", "")
            if any(kw in title.lower() for kw in ["absa", "mastodon", "hashtag", "aspect", "sentiment", "émotion", "emotion"]):
                d = http_delete(f"{KIBANA_URL}/api/saved_objects/visualization/{vid}", timeout=8)
                if d and d.status_code in (200, 204):
                    deleted += 1
    
    r = http_get(f"{KIBANA_URL}/api/saved_objects/_find?type=dashboard&per_page=1000", timeout=12)
    if r and r.status_code == 200:
        for obj in r.json().get("saved_objects", []):
            did = obj.get("id")
            title = obj.get("attributes", {}).get("title", "")
            if any(kw in title.lower() for kw in ["absa", "mastodon"]):
                d = http_delete(f"{KIBANA_URL}/api/saved_objects/dashboard/{did}", timeout=8)
                if d and d.status_code in (200, 204):
                    deleted += 1
    
    print(f"✓ Nettoyage: {deleted} objets supprimés")

# ========================================
# VISUALISATIONS CORRIGÉES
# ========================================

def create_visualization(viz_def, data_view_id):
    vis_state = {
        "title": viz_def["title"],
        "type": viz_def["type"]
    }
    
    if viz_def["type"] == "markdown":
        vis_state["params"] = viz_def.get("params", {})
    else:
        vis_state["aggs"] = viz_def["aggs"]
        vis_state["params"] = viz_def.get("params", {})
    
    search_source = {
        "index": data_view_id,
        "filter": []
    }
    
    if "filter" in viz_def:
        search_source["query"] = {
            "query": viz_def["filter"]["query"],
            "language": viz_def["filter"]["language"]
        }
    else:
        search_source["query"] = {"query": "", "language": "kuery"}
    
    payload = {
        "attributes": {
            "title": viz_def["title"],
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(search_source)
            }
        },
        "references": [{
            "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
            "type": "index-pattern",
            "id": data_view_id
        }]
    }
    
    url = f"{KIBANA_URL}/api/saved_objects/visualization/{viz_def['id']}?overwrite=true"
    r = http_post(url, payload=payload, timeout=12)
    
    if r and r.status_code in (200, 201):
        print(f"  ✓ {viz_def['title']}")
        return True
    
    print(f"  ✗ {viz_def['title']} - {r.status_code if r else 'no response'}")
    return False

def build_visualizations(data_view_id, fields: Dict[str, str]):
    print("\n" + "="*80)
    print("🎨 CRÉATION DES VISUALISATIONS (VERSION FINALE)")
    print("="*80)
    
    ts = int(time.time())
    
    aspects_field = fields.get("aspects", "aspects.keyword")
    hashtags_field = fields.get("hashtags", "metadata.hashtags.keyword")
    sentiment_field = fields.get("sentiment_label", "sentiment.label.keyword")
    emotions_field = fields.get("emotions", "emotions_flat")
    
    print(f"\n🔧 Champs utilisés:")
    print(f"  • aspects: {aspects_field}")
    print(f"  • hashtags: {hashtags_field}")
    print(f"  • sentiment: {sentiment_field}")
    print(f"  • emotions: {emotions_field}\n")
    
    visualizations = [
        # 1. METRIC - Total (CORRIGÉ - structure simplifiée)
        {
            "id": f"viz-metric-total-{ts}",
            "title": "📊 Total Mentions",
            "type": "metric",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "count",
                    "schema": "metric",
                    "params": {}
                }
            ],
            "params": {
                "addTooltip": True,
                "addLegend": False,
                "type": "metric",
                "visColors": pastel_vis_colors(),
                "metric": {
                    "percentageMode": False,
                    "useRanges": False,
                    "colorSchema": "Green to Red",
                    "metricColorMode": "None",
                    "colorsRange": [{"from": 0, "to": 10000}],
                    "labels": {"show": True},
                    "invertColors": False,
                    "style": {
                        "bgFill": "#000",
                        "bgColor": False,
                        "labelColor": False,
                        "subText": "",
                        "fontSize": 60
                    }
                }
            }
        },
        
        # 2. METRIC - Hashtags Uniques (CORRIGÉ)
        {
            "id": f"viz-metric-unique-{ts}",
            "title": "#️⃣ Hashtags Uniques",
            "type": "metric",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "cardinality",
                    "schema": "metric",
                    "params": {
                        "field": hashtags_field
                    }
                }
            ],
            "params": {
                "addTooltip": True,
                "addLegend": False,
                "type": "metric",
                "metric": {
                    "percentageMode": False,
                    "useRanges": False,
                    "colorSchema": "Green to Red",
                    "metricColorMode": "None",
                    "colorsRange": [{"from": 0, "to": 10000}],
                    "labels": {"show": True},
                    "invertColors": False,
                    "style": {
                        "bgFill": "#000",
                        "bgColor": False,
                        "labelColor": False,
                        "subText": "",
                        "fontSize": 60
                    }
                }
            }
        },
        
        # 3. DONUT - Sentiments (avec couleurs pastels)
        {
            "id": f"viz-donut-sent-{ts}",
            "title": "💚 Répartition Sentiments",
            "type": "pie",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "segment", "params": {
                    "field": sentiment_field, "size": 5, "order": "desc", "orderBy": "1"
                }}
            ],
            "params": {
                "type": "pie",
                "addTooltip": True,
                "addLegend": True,
                "legendPosition": "right",
                "isDonut": True,
                "labels": {"show": True, "values": True, "truncate": 100}
            }
        },
        
        # 4. DONUT - Émotions (avec couleurs pastels)
        {
            "id": f"viz-donut-emo-{ts}",
            "title": "😊 Répartition Émotions",
            "type": "pie",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "segment", "params": {
                    "field": emotions_field, "size": 7, "order": "desc", "orderBy": "1"
                }}
            ],
            "params": {
                "type": "pie",
                "addTooltip": True,
                "addLegend": True,
                "legendPosition": "right",
                "isDonut": True,
                "labels": {"show": True, "values": True, "truncate": 100}
            }
        },
        
        # 5. TAG CLOUD - Hashtags
        {
            "id": f"viz-tagcloud-{ts}",
            "title": "☁️ Nuage de Hashtags",
            "type": "tagcloud",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "segment", "params": {
                    "field": hashtags_field, "size": 50, "order": "desc", "orderBy": "1", "min_doc_count": 2
                }}
            ],
            "params": {
                "scale": "linear",
                "orientation": "single",
                "minFontSize": 18,
                "maxFontSize": 72,
                "showLabel": True
            }
        },
        
        # 6. BAR - Top Hashtags
        {
            "id": f"viz-bar-hashtags-{ts}",
            "title": "🔥 Top 15 Hashtags",
            "type": "horizontal_bar",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "segment", "params": {
                    "field": hashtags_field, "size": 15, "order": "desc", "orderBy": "1", "min_doc_count": 5
                }}
            ],
            "params": {
                "type": "histogram",
                "addTooltip": True,
                "addLegend": False,
                "labels": {"show": True, "truncate": 100}
            }
        },
        
        # 7. BAR - Top Aspects
        {
            "id": f"viz-bar-aspects-{ts}",
            "title": "🔎 Top 20 Aspects",
            "type": "horizontal_bar",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "segment", "params": {
                    "field": aspects_field, "size": 20, "order": "desc", "orderBy": "1", "min_doc_count": 5
                }}
            ],
            "params": {
                "type": "histogram",
                "addTooltip": True,
                "addLegend": False,
                "labels": {"show": True, "truncate": 100}
            }
        },
        
        # 8. GROUPED BAR - Sent x Hashtag
        {
            "id": f"viz-group-sent-hashtag-{ts}",
            "title": "📈 Sentiments par Hashtag",
            "type": "histogram",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "segment", "params": {
                    "field": hashtags_field, "size": 12, "order": "desc", "orderBy": "1", "min_doc_count": 10
                }},
                {"id": "3", "type": "terms", "schema": "group", "params": {
                    "field": sentiment_field, "size": 5, "order": "desc", "orderBy": "1"
                }}
            ],
            "params": {
                "type": "histogram",
                "addTooltip": True,
                "addLegend": True,
                "legendPosition": "right",
                "labels": {"show": False},
                "seriesParams": [{
                    "show": True,
                    "type": "histogram",
                    "mode": "grouped",
                    "data": {"label": "Count", "id": "1"},
                    "valueAxis": "ValueAxis-1"
                }]
            }
        },
        
        # 9. GROUPED BAR - Sent x Aspect
        {
            "id": f"viz-group-sent-aspect-{ts}",
            "title": "📈 Sentiments par Aspect",
            "type": "histogram",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "segment", "params": {
                    "field": aspects_field, "size": 15, "order": "desc", "orderBy": "1", "min_doc_count": 10
                }},
                {"id": "3", "type": "terms", "schema": "group", "params": {
                    "field": sentiment_field, "size": 5, "order": "desc", "orderBy": "1"
                }}
            ],
            "params": {
                "type": "histogram",
                "addTooltip": True,
                "addLegend": True,
                "legendPosition": "right",
                "labels": {"show": False},
                "seriesParams": [{
                    "show": True,
                    "type": "histogram",
                    "mode": "grouped",
                    "data": {"label": "Count", "id": "1"},
                    "valueAxis": "ValueAxis-1"
                }]
            }
        },
        
        # 10. TABLE - Aspects Positifs
        {
            "id": f"viz-table-pos-{ts}",
            "title": "✅ Aspects Appréciés",
            "type": "table",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "bucket", "params": {
                    "field": aspects_field, "size": 15, "order": "desc", "orderBy": "1", "min_doc_count": 5
                }},
                {"id": "3", "type": "terms", "schema": "bucket", "params": {
                    "field": hashtags_field, "size": 3, "order": "desc", "orderBy": "1"
                }}
            ],
            "params": {
                "perPage": 15,
                "showPartialRows": False,
                "showMetricsAtAllLevels": True,
                "showTotal": True
            },
            "filter": {
                "query": f'{sentiment_field}:("positive" OR "pos")',
                "language": "kuery"
            }
        },
        
        # 11. TABLE - Aspects Négatifs
        {
            "id": f"viz-table-neg-{ts}",
            "title": "⚠️ Aspects Critiqués",
            "type": "table",
            "aggs": [
                {"id": "1", "type": "count", "schema": "metric", "params": {}},
                {"id": "2", "type": "terms", "schema": "bucket", "params": {
                    "field": aspects_field, "size": 15, "order": "desc", "orderBy": "1", "min_doc_count": 5
                }},
                {"id": "3", "type": "terms", "schema": "bucket", "params": {
                    "field": hashtags_field, "size": 3, "order": "desc", "orderBy": "1"
                }}
            ],
            "params": {
                "perPage": 15,
                "showPartialRows": False,
                "showMetricsAtAllLevels": True,
                "showTotal": True
            },
            "filter": {
                "query": f'{sentiment_field}:("negative" OR "neg")',
                "language": "kuery"
            }
        },
        
        # 12. AREA STACKED - Évolution des Émotions
{
    "id": f"viz-area-emo-{ts}",
    "title": "📊 Évolution des Émotions (7 jours)",
    "type": "area",
    "aggs": [
        {"id": "1", "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "type": "date_histogram", "schema": "segment", "params": {
            "field": "created_at",
            "interval": "auto",
            "min_doc_count": 1
        }},
        {"id": "3", "type": "terms", "schema": "group", "params": {
            "field": emotions_field,
            "size": 7,
            "order": "desc",
            "orderBy": "1"
        }}
    ],
    "params": {
        "type": "area",
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "smoothLines": True,
        "labels": {"show": False},
        "stacked": "stacked"
    }
},

        
        # 13. MARKDOWN - Guide enrichi
        {
            "id": f"viz-guide-{ts}",
            "title": "📖 Guide du Dashboard",
            "type": "markdown",
            "params": {
                "markdown": """# 🎯 Dashboard ABSA - Analyse de Sentiments

---

## 📊 Vue d'ensemble

Ce dashboard analyse en temps réel les **sentiments** et **émotions** des posts Mastodon liés à vos hashtags.

---

## 🔧 Configuration Technique

### Champs mappés
| Champ | Mapping ES |
|-------|-----------|
| **Aspects** | `""" + aspects_field + """` |
| **Hashtags** | `""" + hashtags_field + """` |
| **Sentiments** | `""" + sentiment_field + """` |
| **Émotions** | `""" + emotions_field + """` |

---

## 📈 Lecture des Visualisations

### 💚 Sentiments
- **Positive** : Appréciation, satisfaction
- **Negative** : Critique, insatisfaction
- **Neutral** : Ni positif ni négatif

### 😊 Émotions
- **Joy** (Joie) : Enthousiasme, bonheur
- **Love** (Amour) : Affection, passion
- **Surprise** : Étonnement
- **Sadness** (Tristesse) : Déception
- **Anger** (Colère) : Frustration
- **Fear** (Peur) : Inquiétude
- **Disgust** (Dégoût) : Rejet

---

## 😄 Émotions (Analyse fine)
Les émotions traduisent un **ressenti précis** :

- 🟡 **Joy** → Joie, enthousiasme
- 🌸 **Love** → Attachement, affection
- 😲 **Surprise** → Étonnement
- 🔵 **Sadness** → Déception, tristesse
- 🟠 **Anger** → Colère, mécontentement
- 🟣 **Fear** → Inquiétude
- 🟢 **Disgust** → Rejet

---

## 🎨 Palette pastel officielle

| Couleur | Utilisation |
|-------|------------|
| 🔵 Bleu pastel | Informations générales |
| 🟢 Vert pastel | Sentiments positifs |
| 🔴 Rouge pastel | Sentiments négatifs |
| 🟣 Violet pastel | Neutre |
| 🟡 Jaune pastel | Joie |
| 🌸 Rose pastel | Amour / émotions positives |
| 🟠 Corail pastel | Colère |
| 🔷 Cyan pastel | Tristesse |
| 🟢 Lime pastel | Dégoût |

---

## 📈 Comment lire les graphiques
1. Les **donuts** donnent la proportion
2. Les **barres** montrent les sujets dominants
3. Les **tables** identifient les points forts / faibles
4. Les **tendances temporelles** montrent l’évolution

---

## ⚙️ Paramètres Actifs

- 🔄 **Auto-refresh** : 30 secondes
- ⏰ **Time range** : 7 derniers jours
- 📊 **Minimum docs** : 5 par agrégation

---

## 💡 Insights Clés

✅ **Top Hashtags** : Les sujets les plus discutés
✅ **Top Aspects** : Les entités les plus mentionnées
✅ **Timeline** : L'évolution des émotions dans le temps
✅ **Aspects Appréciés/Critiqués** : Points forts et axes d'amélioration

---

## 🚀 Prochaines Étapes

1. Identifiez les tendances émergentes
2. Analysez les pics d'émotions
3. Comparez les sentiments par hashtag
4. Exportez les données pour rapports

---

*Dashboard créé avec ❤️ pour l'analyse ABSA*
"""
            }
        }
    ]
    
    created_ids = []
    for viz in visualizations:
        if create_visualization(viz, data_view_id):
            created_ids.append(viz["id"])
        time.sleep(0.2)
    
    print(f"\n✓ {len(created_ids)}/13 visualisations créées")
    return created_ids

# ========================================
# DASHBOARD
# ========================================

def create_dashboard(viz_ids, data_view_id):
    if len(viz_ids) < 10:
        print(f"⚠ Seulement {len(viz_ids)}/13 visualisations")
    
    def vid(i):
        return viz_ids[i] if i < len(viz_ids) else None
    
    # Layout optimisé
    panels_src = [
        {"id": vid(0), "x": 0, "y": 0, "w": 12, "h": 8},      # Total Mentions
        {"id": vid(1), "x": 12, "y": 0, "w": 12, "h": 8},     # Hashtags Uniques
        {"id": vid(2), "x": 0, "y": 8, "w": 12, "h": 16},     # Sentiments Donut
        {"id": vid(3), "x": 12, "y": 8, "w": 12, "h": 16},    # Émotions Donut
        {"id": vid(4), "x": 24, "y": 0, "w": 12, "h": 24},    # Tag Cloud
        {"id": vid(5), "x": 0, "y": 24, "w": 18, "h": 16},    # Top Hashtags Bar
        {"id": vid(6), "x": 18, "y": 24, "w": 18, "h": 16},   # Top Aspects Bar
        {"id": vid(7), "x": 0, "y": 40, "w": 18, "h": 16},    # Sent x Hashtag
        {"id": vid(8), "x": 18, "y": 40, "w": 18, "h": 16},   # Sent x Aspect
        {"id": vid(9), "x": 0, "y": 56, "w": 18, "h": 16},    # Aspects Positifs
        {"id": vid(10), "x": 18, "y": 56, "w": 18, "h": 16},  # Aspects Négatifs
        {"id": vid(11), "x": 0, "y": 72, "w": 36, "h": 14},   # Timeline
        {"id": vid(12), "x": 36, "y": 0, "w": 12, "h": 86},   # Guide Markdown
    ]
    
    panels = []
    references = []
    idx = 0
    
    for p in panels_src:
        if not p["id"]:
            continue
        idx += 1
        panels.append({
            "version": "8.11.0",
            "type": "visualization",
            "gridData": {**p, "i": str(idx)},
            "panelIndex": str(idx),
            "embeddableConfig": {},
            "panelRefName": f"panel_{idx}"
        })
        references.append({
            "name": f"panel_{idx}",
            "type": "visualization",
            "id": p["id"]
        })
    
    dashboard_id = f"dash-absa-pastel-{int(time.time())}"
    
    payload = {
        "attributes": {
            "title": "🎨 Dashboard ABSA - Couleurs Pastels",
            "description": "Dashboard ABSA avec palette pastel harmonieuse et markdown enrichi",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({
                "useMargins": True,
                "syncColors": True,
                "syncCursor": True,
                "syncTooltips": True,
                "hidePanelTitles": False
            }),
            "version": 1,
            "timeRestore": True,
            "timeFrom": "now-7d",
            "timeTo": "now",
            "refreshInterval": {"pause": False, "value": 30000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": references
    }
    
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}?overwrite=true"
    r = http_post(url, payload=payload, timeout=15)
    
    if r and r.status_code in (200, 201):
        print("✓ Dashboard créé")
        return dashboard_id
    
    print(f"✗ Échec dashboard: {r.status_code if r else 'no response'}")
    if r:
        print(f"  Response: {r.text[:300]}")
    return None
def pastel_vis_colors():
    return {
        "Positive": PASTEL_COLORS["success"],
        "Negative": PASTEL_COLORS["danger"],
        "Neutral": PASTEL_COLORS["fear"],
        "joy": PASTEL_COLORS["joy"],
        "love": PASTEL_COLORS["love"],
        "surprise": PASTEL_COLORS["surprise"],
        "sadness": PASTEL_COLORS["sadness"],
        "anger": PASTEL_COLORS["anger"],
        "fear": PASTEL_COLORS["fear"],
        "disgust": PASTEL_COLORS["disgust"],
    }


# ========================================
# MAIN
# ========================================

def main():
    print("\n" + "="*80)
    print("🎨 ABSA KIBANA - VERSION PASTELS AMÉLIORÉE")
    print("="*80)
    
    if not check_services():
        sys.exit(1)
    
    index_name = find_best_index()
    if not index_name:
        sys.exit(1)
    
    fields = analyze_mapping(index_name)
    if not fields:
        sys.exit(1)
    
    dv_id = find_existing_data_view("mastodon-trends")
    if not dv_id:
        dv_id = create_or_update_data_view(index_name, "mastodon-trends-pattern")
        if not dv_id:
            sys.exit(1)
    
    deep_cleanup()
    time.sleep(1)
    
    viz_ids = build_visualizations(dv_id, fields)
    if len(viz_ids) < 10:
        print("✗ Trop d'échecs")
        sys.exit(1)
    
    time.sleep(1)
    
    dash_id = create_dashboard(viz_ids, dv_id)
    if not dash_id:
        sys.exit(1)
    
    print("\n" + "="*80)
    print("✅ SUCCESS - DASHBOARD PASTEL CRÉÉ")
    print("="*80)
    print(f"→ Kibana: {KIBANA_URL}/app/dashboards")
    print("→ Titre: '🎨 Dashboard ABSA - Couleurs Pastels'")
    print("\n🎨 Améliorations appliquées:")
    print("  ✓ Palette de couleurs pastels harmonieuses")
    print("  ✓ Métriques simplifiées (Total + Hashtags uniques)")
    print("  ✓ Markdown enrichi avec émojis et tableaux")
    print("  ✓ Time range étendu à 7 jours")
    print("  ✓ Couleurs cohérentes sur tous les graphiques")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✗ Annulé (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
