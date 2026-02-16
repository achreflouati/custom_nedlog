# Documentation - Analyse de Production depuis Sales Order

## Vue d'ensemble

Ce module étend les fonctionnalités de la liste des Sales Orders pour permettre l'analyse directe des besoins de production et la création automatique de Material Requests, en utilisant les mêmes principes que le Production Plan d'ERPNext.

## Fonctionnalités

### 1. Analyse des Besoins de Production

**Bouton**: "Analyse le besoin"

**Fonctionnement**:
- Sélectionner une ou plusieurs Sales Orders
- Cliquer sur "Analyse le besoin"
- Le système affiche une analyse complète avec :
  - Consolidation des items finis
  - Explosion des BOMs
  - Calcul des matières premières nécessaires
  - Vérification des stocks disponibles
  - Identification des manques

### 2. Création Automatique de Material Requests

**Bouton**: "Créer Material Request"

**Fonctionnement**:
- Analyse les besoins comme ci-dessus
- Crée automatiquement les Material Requests pour les items en rupture
- Groupe les demandes par :
  - Fournisseur (si défini)
  - Type de demande (Purchase/Manufacture)
  - Entrepôt

## Architecture Technique

### Fichiers Frontend (JavaScript)
- `/public/js/sales_order_list.js` - Interface utilisateur et gestion des boutons

### Fichiers Backend (Python)
- `/production_analysis.py` - Logique métier principale
- `/permissions.py` - Gestion des permissions
- `/test_production_analysis.py` - Tests unitaires

## Fonctions Principales

### Frontend (JavaScript)

#### `analyze_production_requirements(sales_order_names)`
Lance l'analyse complète des besoins de production.

#### `create_material_requests_from_sales_orders(sales_order_names)`
Crée les Material Requests basées sur l'analyse.

#### `display_production_analysis_results(dialog, analysis_data)`
Affiche les résultats d'analyse dans une interface graphique.

### Backend (Python)

#### `get_sales_orders_with_items(sales_order_names)`
Récupère les Sales Orders avec leurs items et BOMs.

**Retour**:
```python
[{
    'name': 'SO-001',
    'customer': 'Customer Name',
    'items': [{
        'item_code': 'ITEM-001',
        'qty': 10,
        'bom_no': 'BOM-001',
        'warehouse': 'Stores'
    }]
}]
```

#### `analyze_bom_requirements(sales_orders_data)`
Analyse les BOMs et consolide les items.

**Retour**:
```python
{
    'consolidated_items': [...],
    'raw_materials': [...]
}
```

#### `calculate_stock_requirements(consolidated_data)`
Calcule les besoins en stock et disponibilités.

**Retour**:
```python
{
    'consolidated_items': [...],
    'raw_materials_requirements': [...],
    'stats': {
        'total_sales_orders': 3,
        'total_finished_goods': 5,
        'total_raw_materials': 15,
        'items_with_shortage': 7
    }
}
```

#### `create_grouped_material_requests(analysis_data)`
Crée les Material Requests groupées.

**Retour**:
```python
[{
    'name': 'MAT-REQ-001',
    'material_request_type': 'Purchase',
    'supplier': 'Supplier Name',
    'items_count': 5
}]
```

## Logique de Groupement des Material Requests

### Par Fournisseur
- Items avec fournisseur défini → MR séparée par fournisseur
- Items sans fournisseur → MR générale "Purchase"

### Par Type
- **Purchase**: Pour items achetés
- **Manufacture**: Pour items à fabriquer (si BOM existe)
- **Material Transfer**: Pour transferts entre entrepôts

### Par Entrepôt
- Utilise l'entrepôt par défaut de l'item
- Fallback sur l'entrepôt par défaut de la société

## Permissions Requises

Les utilisateurs doivent avoir un des rôles suivants :
- Manufacturing Manager
- Stock Manager  
- Sales Manager
- Purchase Manager

## Interface Utilisateur

### Dialogue d'Analyse
- **Statistiques** : Cartes résumant les données clés
- **Items Consolidés** : Tableau des produits finis à produire
- **Matières Premières** : Tableau détaillé avec stocks et manques

### Dialogue Material Request
- **Résultats de Création** : Liste des MRs créées
- **Liens Directs** : Accès rapide aux documents créés

## Exemple d'Utilisation

1. Aller dans la liste Sales Order
2. Sélectionner les commandes à analyser
3. Cliquer sur "Analyse le besoin"
4. Examiner les résultats d'analyse
5. Si nécessaire, cliquer sur "Créer Material Request"
6. Les MRs sont créées automatiquement et peuvent être traitées

## Intégration avec ERPNext

Ce module s'intègre parfaitement avec :
- **Sales Order** : Source des données
- **BOM** : Explosion des composants
- **Item** : Informations produits et fournisseurs
- **Bin** : Données de stock en temps réel
- **Material Request** : Création automatique
- **Supplier** : Groupement des demandes

## Maintenance et Extension

### Ajouter de Nouvelles Fonctionnalités
1. Ajouter les méthodes Python dans `production_analysis.py`
2. Créer les appels JavaScript correspondants
3. Mettre à jour l'interface si nécessaire

### Modifier l'Interface
1. Éditer les fonctions `generate_*_html()` dans le JavaScript
2. Adapter les styles CSS intégrés

### Tests
Utiliser `test_production_analysis.py` pour valider les modifications.

## Dépannage

### Erreurs Communes

**"Aucun BOM trouvé"**
- Vérifier que les items ont des BOMs actifs
- S'assurer que les BOMs sont soumis (docstatus=1)

**"Erreur de permissions"**
- Vérifier les rôles utilisateur
- Contrôler les permissions sur les doctypes concernés

**"Pas de données retournées"**  
- Vérifier que les Sales Orders sont soumises
- S'assurer qu'il y a des items dans les SO

### Logs de Debug
Les erreurs sont enregistrées dans les logs Frappe avec le préfixe "Erreur production_analysis".