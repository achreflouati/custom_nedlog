# -*- coding: utf-8 -*-
# Copyright (c) 2024, Custom Nedlog and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint, nowdate, add_days
from collections import defaultdict
import json


@frappe.whitelist()
def get_sales_orders_with_items(sales_order_names):
    """
    Récupère les Sales Orders avec leurs items et informations BOM
    """
    try:
        if isinstance(sales_order_names, str):
            sales_order_names = json.loads(sales_order_names)
        
        # Récupérer les Sales Orders
        sales_orders = frappe.get_all(
            'Sales Order',
            filters={'name': ['in', sales_order_names]},
            fields=['name', 'customer', 'transaction_date', 'status', 'company', 'grand_total']
        )
        
        # Récupérer les Sales Order Items avec leurs BOMs
        so_items = frappe.db.sql("""
            SELECT 
                soi.parent as sales_order,
                soi.item_code,
                soi.item_name,
                soi.qty,
                soi.delivered_qty,
                soi.stock_qty,
                soi.warehouse,
                soi.description,
                soi.bom_no,
                item.stock_uom,
                bom.name as default_bom
            FROM `tabSales Order Item` soi
            LEFT JOIN `tabItem` item ON soi.item_code = item.name
            LEFT JOIN `tabBOM` bom ON item.name = bom.item 
                AND bom.is_active = 1 
                AND bom.is_default = 1
                AND bom.docstatus = 1
            WHERE soi.parent IN %(sales_orders)s
            AND soi.docstatus = 1
        """, {'sales_orders': sales_order_names}, as_dict=True)
        
        # Organiser les données par Sales Order
        so_dict = {so.name: so for so in sales_orders}
        
        for item in so_items:
            so_name = item.sales_order
            if so_name in so_dict:
                if 'items' not in so_dict[so_name]:
                    so_dict[so_name]['items'] = []
                
                # Utiliser le BOM défini dans Sales Order Item ou le BOM par défaut
                item['bom_no'] = item.bom_no or item.default_bom
                item['pending_qty'] = flt(item.qty) - flt(item.delivered_qty or 0)
                so_dict[so_name]['items'].append(item)
        
        return list(so_dict.values())
        
    except Exception as e:
        frappe.log_error(f"Erreur get_sales_orders_with_items: {str(e)}")
        frappe.throw(_("Erreur lors de la récupération des Sales Orders: {0}").format(str(e)))


@frappe.whitelist()
def analyze_bom_requirements(sales_orders_data):
    """
    Analyse les BOMs et consolide les items
    """
    try:
        if isinstance(sales_orders_data, str):
            sales_orders_data = json.loads(sales_orders_data)
        
        # DEBUG: Log des données reçues
        debug_msg = f"analyze_bom_requirements - Données reçues: {len(sales_orders_data)} sales orders"
        print(f"DEBUG 1: {debug_msg}")
        
        consolidated_items = {}
        raw_materials_dict = {}
        
        for so_data in sales_orders_data:
            so_msg = f"Traitement Sales Order: {so_data.get('name')}"
            print(f"DEBUG 2: {so_msg}")
            
            items = so_data.get('items', [])
            items_msg = f"Items trouvés: {len(items)}"
            print(f"DEBUG 3: {items_msg}")
            
            for item in items:
                bom_no = item.get('bom_no')
                pending_qty = flt(item.get('pending_qty', 0))
                
                item_msg = f"Item: {item.get('item_code')}, BOM: {bom_no}, Pending Qty: {pending_qty}"
                print(f"DEBUG 4: {item_msg}")
                
                if not bom_no or pending_qty <= 0:
                    ignore_msg = f"Item ignoré - BOM: {bool(bom_no)}, Qty valide: {pending_qty > 0}"
                    print(f"DEBUG 5: {ignore_msg}")
                    continue
                
                process_msg = f"Item traité: {item.get('item_code')}"
                print(f"DEBUG 6: {process_msg}")
                
                item_key = (item['item_code'], item.get('warehouse', ''))
                
                # Consolidation des items finis
                if item_key not in consolidated_items:
                    consolidated_items[item_key] = {
                        'item_code': item['item_code'],
                        'item_name': item.get('item_name', item['item_code']),
                        'description': item.get('description', ''),
                        'bom_no': bom_no,
                        'warehouse': item.get('warehouse', ''),
                        'stock_uom': item.get('stock_uom', 'Nos'),
                        'total_qty': 0,
                        'sales_orders': []
                    }
                
                consolidated_items[item_key]['total_qty'] += pending_qty
                consolidated_items[item_key]['sales_orders'].append({
                    'sales_order': so_data['name'],
                    'customer': so_data.get('customer', ''),
                    'qty': pending_qty
                })
                
                # Analyse des matières premières du BOM
                bom_materials = get_bom_raw_materials(bom_no, pending_qty)
                bom_msg = f"BOM {bom_no} - Matières trouvées: {len(bom_materials)}"
                print(f"DEBUG 7: {bom_msg}")
                
                for material in bom_materials:
                    material_key = material['item_code']
                    
                    if material_key not in raw_materials_dict:
                        raw_materials_dict[material_key] = {
                            'item_code': material['item_code'],
                            'item_name': material['item_name'],
                            'stock_uom': material['stock_uom'],
                            'required_qty': 0,
                            'source_items': []
                        }
                    material_key = material['item_code']
                    
                    if material_key not in raw_materials_dict:
                        raw_materials_dict[material_key] = {
                            'item_code': material['item_code'],
                            'item_name': material['item_name'],
                            'stock_uom': material['stock_uom'],
                            'required_qty': 0,
                            'source_items': []
                        }
                    
                    raw_materials_dict[material_key]['required_qty'] += material['required_qty']
                    raw_materials_dict[material_key]['source_items'].append({
                        'finished_good': item['item_code'],
                        'bom_no': bom_no,
                        'qty_needed': material['required_qty'],
                        'sales_order': so_data['name']
                    })
        
        # DEBUG: Log final
        final_msg = f"Résultats finaux - Items consolidés: {len(consolidated_items)}, Matières: {len(raw_materials_dict)}"
        print(f"DEBUG 8: {final_msg}")
        
        result = {
            'consolidated_items': list(consolidated_items.values()),
            'raw_materials': list(raw_materials_dict.values())
        }
        
        return_msg = f"Retour des résultats: {len(result['consolidated_items'])} items, {len(result['raw_materials'])} matières"
        print(f"DEBUG 9: {return_msg}")
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Erreur analyze_bom_requirements: {str(e)}")
        print(f"ERREUR: {str(e)}")
        frappe.throw(_("Erreur lors de l'analyse des BOMs: {0}").format(str(e)))


def get_bom_raw_materials(bom_no, required_qty):
    """
    Récupère les matières premières d'un BOM avec explosion complète
    """
    try:
        if not bom_no:
            print(f"DEBUG BOM: Pas de BOM fourni")
            return []
        
        print(f"DEBUG BOM: Recherche BOM {bom_no}")
        
        # Récupérer le document BOM
        bom_doc = frappe.get_doc("BOM", bom_no)
        if not bom_doc:
            print(f"DEBUG BOM: Document BOM {bom_no} introuvable")
            return []
        
        print(f"DEBUG BOM: Document trouvé, quantity={bom_doc.quantity}")
        
        # Récupérer les items du BOM
        bom_items = frappe.get_all(
            "BOM Item",
            filters={
                "parent": bom_no,
                "parenttype": "BOM"
            },
            fields=[
                "item_code", "item_name", "qty", "stock_uom", "description"
            ]
        )
        
        print(f"DEBUG BOM: BOM Items trouvés: {len(bom_items)}")
        
        if not bom_items:
            print(f"DEBUG BOM: Aucun item trouvé pour BOM {bom_no}")
            return []
        
        materials = []
        bom_qty = flt(bom_doc.quantity) or 1
        
        print(f"DEBUG BOM: Quantité BOM: {bom_qty}, Required qty: {required_qty}")
        
        for i, bom_item in enumerate(bom_items):
            print(f"DEBUG BOM: Item {i+1}/{len(bom_items)}: {bom_item.item_code}, qty: {bom_item.qty}")
            
            # Calculer les quantités
            qty_per_unit = flt(bom_item.qty) / bom_qty
            total_qty_needed = qty_per_unit * flt(required_qty)
            
            print(f"DEBUG BOM: Calcul - qty_per_unit: {qty_per_unit}, total_needed: {total_qty_needed}")
            
            # Récupérer le fournisseur principal de l'item (première tentative sans is_default)
            try:
                default_supplier = frappe.db.get_value(
                    "Item Supplier",
                    {"parent": bom_item.item_code},
                    "supplier"
                )
            except Exception as supplier_error:
                print(f"DEBUG BOM: Erreur récupération fournisseur: {supplier_error}")
                default_supplier = None
            
            # Récupérer les infos de l'item
            try:
                item_info = frappe.db.get_value(
                    "Item", 
                    bom_item.item_code, 
                    ["stock_uom", "is_stock_item"], 
                    as_dict=True
                ) or {}
            except Exception as item_error:
                print(f"DEBUG BOM: Erreur récupération item info: {item_error}")
                item_info = {}
            
            material = {
                'item_code': bom_item.item_code,
                'item_name': bom_item.item_name or bom_item.item_code,
                'stock_uom': bom_item.stock_uom or item_info.get('stock_uom', 'Nos'),
                'qty_per_unit': qty_per_unit,
                'required_qty': total_qty_needed,
                'description': bom_item.description or '',
                'is_stock_item': item_info.get('is_stock_item', 1),
                'default_supplier': default_supplier
            }
            
            materials.append(material)
            print(f"DEBUG BOM: Material ajouté: {bom_item.item_code}, qty: {total_qty_needed}")
        
        print(f"DEBUG BOM: Total materials créés: {len(materials)}")
        return materials
        
    except Exception as e:
        print(f"DEBUG BOM ERREUR: {str(e)}")
        frappe.log_error(f"Erreur BOM {bom_no}: {str(e)}")
        return []


@frappe.whitelist()
def calculate_stock_requirements(consolidated_data):
    """
    Calcule les besoins en stock et les disponibilités
    """
    try:
        if isinstance(consolidated_data, str):
            consolidated_data = json.loads(consolidated_data)
        
        raw_materials = consolidated_data.get('raw_materials', [])
        
        # Récupérer les informations de stock pour tous les items
        item_codes = [rm['item_code'] for rm in raw_materials]
        
        if not item_codes:
            return {
                'consolidated_items': consolidated_data.get('consolidated_items', []),
                'raw_materials_requirements': [],
                'stats': get_analysis_stats(consolidated_data, [])
            }
        
        # Récupérer les stocks disponibles
        stock_data = frappe.db.sql("""
            SELECT 
                item_code,
                warehouse,
                actual_qty,
                projected_qty,
                reserved_qty,
                ordered_qty,
                planned_qty
            FROM `tabBin`
            WHERE item_code IN %(item_codes)s
            AND actual_qty > 0
        """, {'item_codes': item_codes}, as_dict=True)
        
        # Organiser les stocks par item
        stock_by_item = defaultdict(lambda: {
            'actual_qty': 0,
            'projected_qty': 0,
            'reserved_qty': 0,
            'warehouses': []
        })
        
        for stock in stock_data:
            item_code = stock['item_code']
            stock_by_item[item_code]['actual_qty'] += flt(stock['actual_qty'])
            stock_by_item[item_code]['projected_qty'] += flt(stock['projected_qty'])
            stock_by_item[item_code]['reserved_qty'] += flt(stock['reserved_qty'])
            stock_by_item[item_code]['warehouses'].append({
                'warehouse': stock['warehouse'],
                'actual_qty': stock['actual_qty'],
                'projected_qty': stock['projected_qty']
            })
        
        # Récupérer les informations fournisseurs
        try:
            supplier_data = frappe.db.sql("""
                SELECT 
                    parent as item_code,
                    supplier,
                    supplier_name
                FROM `tabItem Supplier`
                WHERE parent IN %(item_codes)s
            """, {'item_codes': item_codes}, as_dict=True)
        except Exception as supplier_error:
            print(f"DEBUG: Erreur requête fournisseur: {supplier_error}")
            # Fallback - essayer sans supplier_name
            try:
                supplier_data = frappe.db.sql("""
                    SELECT 
                        parent as item_code,
                        supplier
                    FROM `tabItem Supplier`
                    WHERE parent IN %(item_codes)s
                """, {'item_codes': item_codes}, as_dict=True)
            except Exception as fallback_error:
                print(f"DEBUG: Erreur fallback fournisseur: {fallback_error}")
                supplier_data = []
        
        supplier_by_item = {s['item_code']: s for s in supplier_data}
        print(f"DEBUG: Fournisseurs trouvés: {len(supplier_data)}")
        
        # Calculer les besoins finaux
        raw_materials_requirements = []
        
        for material in raw_materials:
            item_code = material['item_code']
            required_qty = flt(material['required_qty'])
            stock_info = stock_by_item.get(item_code, {})
            available_qty = flt(stock_info.get('projected_qty', 0))
            shortage_qty = max(0, required_qty - available_qty)
            
            supplier_info = supplier_by_item.get(item_code, {})
            
            raw_materials_requirements.append({
                'item_code': item_code,
                'item_name': material['item_name'],
                'stock_uom': material['stock_uom'],
                'required_qty': required_qty,
                'available_qty': available_qty,
                'shortage_qty': shortage_qty,
                'actual_qty': stock_info.get('actual_qty', 0),
                'reserved_qty': stock_info.get('reserved_qty', 0),
                'warehouses': stock_info.get('warehouses', []),
                'default_supplier': supplier_info.get('supplier'),
                'supplier_name': supplier_info.get('supplier_name'),
                'source_items': material.get('source_items', []),
                'has_shortage': shortage_qty > 0
            })
        
        return {
            'consolidated_items': consolidated_data.get('consolidated_items', []),
            'raw_materials_requirements': raw_materials_requirements,
            'stats': get_analysis_stats(consolidated_data, raw_materials_requirements)
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur calculate_stock_requirements: {str(e)}")
        frappe.throw(_("Erreur lors du calcul des stocks: {0}").format(str(e)))


def get_analysis_stats(consolidated_data, raw_materials_requirements):
    """
    Calcule les statistiques pour l'affichage
    """
    consolidated_items = consolidated_data.get('consolidated_items', [])
    
    return {
        'total_sales_orders': len(set([
            so['sales_order'] 
            for item in consolidated_items 
            for so in item.get('sales_orders', [])
        ])),
        'total_finished_goods': len(consolidated_items),
        'total_raw_materials': len(raw_materials_requirements),
        'items_with_shortage': len([rm for rm in raw_materials_requirements if rm.get('has_shortage', False)])
    }


@frappe.whitelist()
def create_grouped_material_requests(analysis_data):
    """
    Crée les Material Requests groupées par fournisseur et type
    """
    try:
        if isinstance(analysis_data, str):
            analysis_data = json.loads(analysis_data)
        
        raw_materials = analysis_data.get('raw_materials_requirements', [])
        
        # Filtrer uniquement les items avec shortage
        items_with_shortage = [rm for rm in raw_materials if rm.get('has_shortage', False) and rm.get('shortage_qty', 0) > 0]
        
        if not items_with_shortage:
            return []
        
        # Grouper par fournisseur et type de demande
        grouped_materials = defaultdict(list)
        
        for material in items_with_shortage:
            # Déterminer le type de Material Request
            supplier = material.get('default_supplier')
            if supplier:
                # Purchase Request pour items avec fournisseur
                key = f"Purchase_{supplier}"
                material_request_type = "Purchase"
            else:
                # Material Request général pour items sans fournisseur
                key = "Purchase_No_Supplier"
                material_request_type = "Purchase"
            
            grouped_materials[key].append({
                **material,
                'material_request_type': material_request_type,
                'supplier': supplier
            })
        
        # Créer les Material Requests
        created_mrs = []
        
        for group_key, materials in grouped_materials.items():
            try:
                mr_doc = create_single_material_request(materials, group_key)
                if mr_doc:
                    created_mrs.append({
                        'name': mr_doc.name,
                        'material_request_type': mr_doc.material_request_type,
                        'supplier': materials[0].get('supplier_name') or materials[0].get('supplier'),
                        'warehouse': get_default_warehouse(),
                        'items_count': len(materials),
                        'status': mr_doc.status
                    })
            except Exception as e:
                frappe.log_error(f"Erreur création MR pour {group_key}: {str(e)}")
                continue
        
        return created_mrs
        
    except Exception as e:
        frappe.log_error(f"Erreur create_grouped_material_requests: {str(e)}")
        frappe.throw(_("Erreur lors de la création des Material Requests: {0}").format(str(e)))


def create_single_material_request(materials, group_key):
    """
    Crée une Material Request pour un groupe de matériaux
    """
    try:
        # Créer le document Material Request
        mr = frappe.new_doc("Material Request")
        mr.material_request_type = materials[0]['material_request_type']
        mr.transaction_date = nowdate()
        mr.schedule_date = add_days(nowdate(), 7)  # 7 jours par défaut
        mr.company = frappe.defaults.get_defaults().get('company')
        mr.status = "Draft"
        
        # Ajouter une note explicative
        source_sales_orders = set()
        for material in materials:
            for source in material.get('source_items', []):
                source_sales_orders.add(source.get('sales_order'))
        
        mr.remarks = f"Material Request créée automatiquement pour Sales Orders: {', '.join(source_sales_orders)}"
        
        # Ajouter les items
        for material in materials:
            mr.append("items", {
                "item_code": material['item_code'],
                "item_name": material['item_name'],
                "qty": material['shortage_qty'],
                "uom": material['stock_uom'],
                "warehouse": get_default_warehouse_for_item(material['item_code']),
                "schedule_date": add_days(nowdate(), 7),
                "description": f"Requis pour production - Manque: {material['shortage_qty']}"
            })
        
        # Sauvegarder le document
        mr.insert(ignore_permissions=True)
        
        return mr
        
    except Exception as e:
        frappe.log_error(f"Erreur create_single_material_request: {str(e)}")
        return None


def get_default_warehouse():
    """
    Récupère l'entrepôt par défaut
    """
    company = frappe.defaults.get_defaults().get('company')
    if company:
        warehouse = frappe.db.get_value("Company", company, "default_warehouse")
        if warehouse:
            return warehouse
    
    # Fallback: premier entrepôt trouvé
    warehouse = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
    return warehouse


def get_default_warehouse_for_item(item_code):
    """
    Récupère l'entrepôt par défaut pour un item spécifique
    """
    # D'abord essayer l'entrepôt par défaut de l'item
    default_warehouse = frappe.db.get_value("Item", item_code, "default_warehouse")
    
    if default_warehouse:
        return default_warehouse
    
    # Sinon, utiliser l'entrepôt par défaut général
    return get_default_warehouse()


@frappe.whitelist()
def get_available_boms_for_item(item_code):
    """
    Récupère tous les BOMs disponibles pour un item
    """
    try:
        boms = frappe.get_all("BOM", 
            filters={"item": item_code},
            fields=["name", "item", "is_active", "is_default", "docstatus", "quantity", "creation"],
            order_by="creation desc"
        )
        
        result = {
            "item_code": item_code,
            "total_boms": len(boms),
            "active_boms": len([b for b in boms if b.is_active]),
            "default_boms": len([b for b in boms if b.is_default]),
            "submitted_boms": len([b for b in boms if b.docstatus == 1]),
            "valid_boms": len([b for b in boms if b.is_active and b.is_default and b.docstatus == 1]),
            "boms": boms
        }
        
        frappe.log_error(f"Item {item_code}: {result['total_boms']} BOMs trouvés, {result['valid_boms']} valides")
        return result
        
    except Exception as e:
        frappe.log_error(f"Erreur get_available_boms_for_item: {str(e)}")
        return {"error": str(e)}


@frappe.whitelist()
def debug_bom_analysis(bom_no, qty=1):
    """
    Fonction de debug pour tester l'analyse d'un BOM spécifique
    """
    try:
        frappe.log_error(f"=== DEBUG BOM ANALYSIS START ===")
        frappe.log_error(f"BOM: {bom_no}, Qty: {qty}")
        
        # Test 1: Vérifier l'existence du BOM
        bom_exists = frappe.db.exists("BOM", bom_no)
        frappe.log_error(f"BOM existe: {bom_exists}")
        
        if bom_exists:
            # Test 2: Récupérer le document BOM
            bom_doc = frappe.get_doc("BOM", bom_no)
            frappe.log_error(f"BOM Doc - Actif: {bom_doc.is_active}, Par défaut: {bom_doc.is_default}, Statut: {bom_doc.docstatus}, Item: {bom_doc.item}")
            
            # Test 3: Vérifier si le BOM est valide pour notre analyse
            is_valid_bom = bom_doc.is_active and bom_doc.is_default and bom_doc.docstatus == 1
            frappe.log_error(f"BOM valide pour analyse: {is_valid_bom}")
            
            # Test 4: Récupérer les BOM Items
            bom_items = frappe.get_all("BOM Item", 
                filters={"parent": bom_no}, 
                fields=["item_code", "item_name", "qty", "stock_uom"])
            frappe.log_error(f"BOM Items trouvés: {len(bom_items)}")
            
            for item in bom_items:
                frappe.log_error(f"  - {item.item_code}: {item.qty} {item.stock_uom}")
            
            # Test 5: Appeler notre fonction
            materials = get_bom_raw_materials(bom_no, qty)
            frappe.log_error(f"Matières calculées: {len(materials)}")
            
            result = {
                "bom_exists": bom_exists,
                "bom_active": bom_doc.is_active if bom_doc else False,
                "bom_default": bom_doc.is_default if bom_doc else False,
                "bom_status": bom_doc.docstatus if bom_doc else 0,
                "bom_valid": is_valid_bom,
                "bom_items_count": len(bom_items),
                "materials_count": len(materials),
                "materials": materials
            }
            
            frappe.log_error(f"=== DEBUG BOM ANALYSIS END ===")
            return result
        else:
            return {"error": f"BOM {bom_no} n'existe pas"}
            
    except Exception as e:
        frappe.log_error(f"Erreur debug_bom_analysis: {str(e)}")
        return {"error": str(e)}


# ================== FONCTIONS UTILITAIRES ==================

def get_company_default_warehouse(company=None):
    """
    Récupère l'entrepôt par défaut de la société
    """
    if not company:
        company = frappe.defaults.get_defaults().get('company')
    
    if company:
        return frappe.db.get_value("Company", company, "default_warehouse")
    
    return None


def validate_bom_exists(item_code):
    """
    Vérifie qu'un BOM existe pour l'item
    """
    return frappe.db.exists("BOM", {
        "item": item_code,
        "is_active": 1,
        "docstatus": 1
    })


def get_item_stock_summary(item_code):
    """
    Récupère un résumé du stock pour un item
    """
    return frappe.db.sql("""
        SELECT 
            SUM(actual_qty) as total_actual,
            SUM(projected_qty) as total_projected,
            SUM(reserved_qty) as total_reserved,
            COUNT(DISTINCT warehouse) as warehouse_count
        FROM `tabBin`
        WHERE item_code = %(item_code)s
    """, {'item_code': item_code}, as_dict=True)[0]