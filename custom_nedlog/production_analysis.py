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
            fields=['name', 'customer', 'transaction_date', 'status', 'company', 'grand_total', 'po_no']
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
    Analyse les BOMs et maintient les détails par Sales Order (pas de consolidation)
    """
    try:
        if isinstance(sales_orders_data, str):
            sales_orders_data = json.loads(sales_orders_data)
        
        consolidated_items = {}
        raw_materials_by_order = []  # Liste des matières premières par order
        
        for so_data in sales_orders_data:
            items = so_data.get('items', [])
            
            for item in items:
                bom_no = item.get('bom_no')
                pending_qty = flt(item.get('pending_qty', 0))
                
                if not bom_no or pending_qty <= 0:
                    continue
                
                item_key = (item['item_code'], item.get('warehouse', ''))
                
                # Consolidation des items finis (garde cette logique)
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
                    'customer_po_no': so_data.get('po_no', ''),
                    'qty': pending_qty
                })
                
                # Analyse des matières premières du BOM - GARDER PAR ORDER
                bom_materials = get_bom_raw_materials(bom_no, pending_qty)
                
                for material in bom_materials:
                    # Ajouter chaque matière première avec ses détails de commande
                    raw_materials_by_order.append({
                        'item_code': material['item_code'],
                        'item_name': material['item_name'],
                        'stock_uom': material['stock_uom'],
                        'required_qty': material['required_qty'],
                        'sales_order': so_data['name'],
                        'customer': so_data.get('customer', ''),
                        'customer_po_no': so_data.get('po_no', ''),
                        'finished_good': item['item_code'],
                        'bom_no': bom_no,
                        'default_supplier': material.get('default_supplier')
                    })
        
        result = {
            'consolidated_items': list(consolidated_items.values()),
            'raw_materials_by_order': raw_materials_by_order
        }
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Erreur analyze_bom_requirements: {str(e)}")
        frappe.throw(_("Erreur lors de l'analyse des BOMs: {0}").format(str(e)))


def get_bom_raw_materials(bom_no, required_qty):
    """
    Récupère les matières premières d'un BOM avec explosion complète
    """
    try:
        if not bom_no:
            return []
        
        # Récupérer le document BOM
        bom_doc = frappe.get_doc("BOM", bom_no)
        if not bom_doc:
            return []
        
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
        
        if not bom_items:
            return []
        
        materials = []
        bom_qty = flt(bom_doc.quantity) or 1
        
        for bom_item in bom_items:
            # Calculer les quantités
            qty_per_unit = flt(bom_item.qty) / bom_qty
            total_qty_needed = qty_per_unit * flt(required_qty)
            
            # Récupérer le fournisseur principal de l'item
            try:
                default_supplier = frappe.db.get_value(
                    "Item Supplier",
                    {"parent": bom_item.item_code},
                    "supplier"
                )
            except Exception:
                default_supplier = None
            
            # Récupérer les infos de l'item
            try:
                item_info = frappe.db.get_value(
                    "Item", 
                    bom_item.item_code, 
                    ["stock_uom", "is_stock_item"], 
                    as_dict=True
                ) or {}
            except Exception:
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
        
        return materials
        
    except Exception as e:
        frappe.log_error(f"Erreur BOM {bom_no}: {str(e)}")
        return []


@frappe.whitelist()
def calculate_stock_requirements(consolidated_data):
    """
    Calcule les besoins en stock par order et ajoute les totaux
    """
    try:
        if isinstance(consolidated_data, str):
            consolidated_data = json.loads(consolidated_data)
        
        raw_materials_by_order = consolidated_data.get('raw_materials_by_order', [])
        
        if not raw_materials_by_order:
            return {
                'consolidated_items': consolidated_data.get('consolidated_items', []),
                'raw_materials_requirements': [],
                'stats': get_analysis_stats(consolidated_data, [])
            }
        
        # Récupérer tous les item codes uniques
        item_codes = list(set([rm['item_code'] for rm in raw_materials_by_order]))
        
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
            AND actual_qty != 0
        """, {'item_codes': item_codes}, as_dict=True)
        
        # Organiser les stocks par item
        stock_by_item = defaultdict(lambda: {
            'actual_qty': 0,
            'projected_qty': 0,
            'reserved_qty': 0,
            'warehouses': [],
            'warehouses_with_stock': [],
            'total_warehouses': 0
        })
        
        for stock in stock_data:
            item_code = stock['item_code']
            stock_by_item[item_code]['actual_qty'] += flt(stock['actual_qty'])
            stock_by_item[item_code]['projected_qty'] += flt(stock['projected_qty'])
            stock_by_item[item_code]['reserved_qty'] += flt(stock['reserved_qty'])
            
            # Toujours ajouter le warehouse pour avoir la liste complète
            stock_by_item[item_code]['warehouses'].append({
                'warehouse': stock['warehouse'],
                'actual_qty': stock['actual_qty'],
                'projected_qty': stock['projected_qty'],
                'reserved_qty': stock['reserved_qty']
            })
            
            # Ajouter seulement les warehouses avec stock positif
            if flt(stock['actual_qty']) > 0:
                stock_by_item[item_code]['warehouses_with_stock'].append({
                    'warehouse': stock['warehouse'],
                    'actual_qty': stock['actual_qty'],
                    'projected_qty': stock['projected_qty'],
                    'reserved_qty': stock['reserved_qty']
                })
            
            stock_by_item[item_code]['total_warehouses'] = len(stock_by_item[item_code]['warehouses'])
        
        # Récupérer les informations fournisseurs
        try:
            supplier_data = frappe.db.sql("""
                SELECT 
                    parent as item_code,
                    supplier
                FROM `tabItem Supplier`
                WHERE parent IN %(item_codes)s
            """, {'item_codes': item_codes}, as_dict=True)
        except Exception:
            supplier_data = []
        
        # Récupérer les informations supplémentaires des items
        try:
            item_extra_data = frappe.db.sql("""
                SELECT 
                    name as item_code,
                    item_group,
                    brand,
                    weight_per_unit,
                    weight_uom
                FROM `tabItem`
                WHERE name IN %(item_codes)s
            """, {'item_codes': item_codes}, as_dict=True)
        except Exception:
            item_extra_data = []
        
        # Récupérer les informations customer provided items
        try:
            client_data = frappe.get_all(
                "Item",
                filters={
                    "name": ["in", item_codes],
                    "is_customer_provided_item": 1,
                    "customer": ["is", "set"]
                },
                fields=["name as item_code", "customer as client_code", "is_customer_provided_item"]
            )
        except Exception as e:
            frappe.log_error(f"Erreur lors de la récupération des customer provided items: {str(e)}")
            client_data = []
        
        supplier_by_item = {s['item_code']: s for s in supplier_data}
        item_extra_by_item = {i['item_code']: i for i in item_extra_data}
        client_by_item = {c['item_code']: c for c in client_data}
        
        # Enrichir les données client avec les noms
        for item_code, client_info in client_by_item.items():
            if client_info.get('client_code'):
                try:
                    customer_name = frappe.db.get_value("Customer", client_info['client_code'], "customer_name")
                    client_info['client_name'] = customer_name or client_info['client_code']
                except Exception:
                    client_info['client_name'] = client_info['client_code']
        
        # Enrichir les données fournisseur avec les noms
        for item_code, supplier_info in supplier_by_item.items():
            if supplier_info.get('supplier'):
                try:
                    supplier_name = frappe.db.get_value("Supplier", supplier_info['supplier'], "supplier_name")
                    supplier_info['supplier_name'] = supplier_name or supplier_info['supplier']
                except Exception:
                    supplier_info['supplier_name'] = supplier_info['supplier']
        
        # Préparer les résultats détaillés par order + totaux
        detailed_requirements = []
        totals_by_item = {}
        
        # Traiter chaque ligne de matière première
        for material in raw_materials_by_order:
            item_code = material['item_code']
            required_qty = flt(material['required_qty'])
            
            supplier_info = supplier_by_item.get(item_code, {})
            client_info = client_by_item.get(item_code, {})
            stock_info = stock_by_item.get(item_code, {})
            item_extra_info = item_extra_by_item.get(item_code, {})
            
            # Déterminer si c'est un customer provided item
            is_customer_provided = client_info.get('is_customer_provided_item', False)
            
            # Pour l'affichage: si c'est un customer provided item, utiliser le client comme "fournisseur"
            display_supplier_name = client_info.get('client_name') if is_customer_provided else supplier_info.get('supplier_name')
            display_supplier_code = client_info.get('client_code') if is_customer_provided else supplier_info.get('supplier')
            
            # Ajouter la ligne détaillée
            detail_row = {
                'type': 'detail',  # Identifier comme ligne de détail
                'item_code': item_code,
                'item_name': material['item_name'],
                'stock_uom': material['stock_uom'],
                'required_qty': required_qty,
                'sales_order': material['sales_order'],
                'customer_po_no': material['customer_po_no'],
                'customer': material['customer'],
                'default_supplier': display_supplier_code,
                'supplier_name': display_supplier_name,
                'is_customer_provided_item': is_customer_provided,
                'customer_provided_client': client_info.get('client_code'),
                'customer_provided_client_name': client_info.get('client_name'),
                'actual_qty': stock_info.get('actual_qty', 0),
                'projected_qty': stock_info.get('projected_qty', 0),
                'warehouses': stock_info.get('warehouses', []),
                # Informations supplémentaires des items
                'item_group': item_extra_info.get('item_group', ''),
                'brand': item_extra_info.get('brand', ''),
                'weight_per_unit': item_extra_info.get('weight_per_unit', ''),
                'weight_uom': item_extra_info.get('weight_uom', ''),
                # Informations des warehouses pour les détails
                'warehouses': [],  # Pas de warehouses pour les détails
                'warehouses_with_stock': [],
                'total_warehouses': 0
            }
            
            detailed_requirements.append(detail_row)
            
            # Accumuler pour les totaux
            if item_code not in totals_by_item:
                totals_by_item[item_code] = {
                    'type': 'total',  # Identifier comme ligne de total
                    'item_code': item_code,
                    'item_name': material['item_name'],
                    'stock_uom': material['stock_uom'],
                    'total_required_qty': 0,
                    'available_qty': stock_info.get('projected_qty', 0),
                    'shortage_qty': 0,
                    'default_supplier': display_supplier_code,
                    'supplier_name': display_supplier_name,
                    'is_customer_provided_item': is_customer_provided,
                    'customer_provided_client': client_info.get('client_code'),
                    'customer_provided_client_name': client_info.get('client_name'),
                    'actual_qty': stock_info.get('actual_qty', 0),
                    'warehouses': stock_info.get('warehouses', []),
                    'warehouses_with_stock': stock_info.get('warehouses_with_stock', []),
                    'total_warehouses': stock_info.get('total_warehouses', 0),
                    'orders_count': 0,
                    # Informations supplémentaires des items
                    'item_group': item_extra_info.get('item_group', ''),
                    'brand': item_extra_info.get('brand', ''),
                    'weight_per_unit': item_extra_info.get('weight_per_unit', ''),
                    'weight_uom': item_extra_info.get('weight_uom', '')
                }
            
            totals_by_item[item_code]['total_required_qty'] += required_qty
            totals_by_item[item_code]['orders_count'] += 1
        
        # Calculer les shortages pour les totaux
        for item_code, total_data in totals_by_item.items():
            shortage = max(0, total_data['total_required_qty'] - total_data['available_qty'])
            total_data['shortage_qty'] = shortage
            total_data['has_shortage'] = shortage > 0
        
        # Combiner détails et totaux
        final_requirements = detailed_requirements + list(totals_by_item.values())
        
        return {
            'consolidated_items': consolidated_data.get('consolidated_items', []),
            'raw_materials_requirements': final_requirements,
            'stats': get_analysis_stats_detailed(consolidated_data, final_requirements)
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur calculate_stock_requirements: {str(e)}")
        frappe.throw(_("Erreur lors du calcul des stocks: {0}").format(str(e)))


def get_analysis_stats_detailed(consolidated_data, raw_materials_requirements):
    """
    Calcule les statistiques pour l'affichage avec la nouvelle structure détaillée
    """
    consolidated_items = consolidated_data.get('consolidated_items', [])
    
    # Séparer les détails des totaux
    details = [rm for rm in raw_materials_requirements if rm.get('type') == 'detail']
    totals = [rm for rm in raw_materials_requirements if rm.get('type') == 'total']
    
    return {
        'total_sales_orders': len(set([
            so['sales_order'] 
            for item in consolidated_items 
            for so in item.get('sales_orders', [])
        ])),
        'total_finished_goods': len(consolidated_items),
        'total_raw_materials_unique': len(totals),
        'total_raw_materials_lines': len(details),
        'items_with_shortage': len([rm for rm in totals if rm.get('has_shortage', False)])
    }


def get_analysis_stats(consolidated_data, raw_materials_requirements):
    """
    Calcule les statistiques pour l'affichage (version compatible)
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
    Crée les Material Requests groupées par fournisseur et type (version adaptée aux détails)
    """
    try:
        if isinstance(analysis_data, str):
            analysis_data = json.loads(analysis_data)
        
        raw_materials = analysis_data.get('raw_materials_requirements', [])
        
        # Filtrer uniquement les totaux avec shortage
        totals_with_shortage = [
            rm for rm in raw_materials 
            if rm.get('type') == 'total' and rm.get('has_shortage', False) and rm.get('shortage_qty', 0) > 0
        ]
        
        if not totals_with_shortage:
            return []
        
        # Grouper par fournisseur/client et type de demande
        grouped_materials = defaultdict(list)
        
        for material in totals_with_shortage:
            # Déterminer le type de Material Request selon la priorité
            if material.get('is_customer_provided_item', False) and material.get('customer_provided_client'):
                # PRIORITY 1: Customer Provided Items
                client_code = material.get('customer_provided_client')
                client_name = material.get('customer_provided_client_name', client_code)
                key = f"CustomerProvided_{client_code}"
                material_request_type = "Purchase"
                provider_info = {
                    'type': 'customer_provided',
                    'code': client_code,
                    'name': client_name
                }
            elif material.get('default_supplier'):
                # PRIORITY 2: Supplier normal
                supplier = material.get('default_supplier')
                supplier_name = material.get('supplier_name') or supplier
                key = f"Purchase_{supplier}"
                material_request_type = "Purchase"
                provider_info = {
                    'type': 'supplier',
                    'code': supplier,
                    'name': supplier_name
                }
            else:
                # PRIORITY 3: Aucun fournisseur défini
                key = "Purchase_No_Provider"
                material_request_type = "Purchase"
                provider_info = {
                    'type': 'no_provider',
                    'code': None,
                    'name': 'Pas de fournisseur défini'
                }
            
            # Adapter la structure pour la création de MR
            mr_material = {
                'item_code': material['item_code'],
                'item_name': material['item_name'],
                'stock_uom': material['stock_uom'],
                'shortage_qty': material['shortage_qty'],
                'material_request_type': material_request_type,
                'provider_info': provider_info
            }
            
            grouped_materials[key].append(mr_material)
        
        # Créer les Material Requests
        created_mrs = []
        
        for group_key, materials in grouped_materials.items():
            try:
                mr_doc = create_single_material_request(materials, group_key)
                if mr_doc:
                    provider_info = materials[0].get('provider_info', {})
                    
                    created_mrs.append({
                        'name': mr_doc.name,
                        'material_request_type': mr_doc.material_request_type,
                        'provider_type': provider_info.get('type'),
                        'provider_code': provider_info.get('code'),
                        'provider_name': provider_info.get('name'),
                        'supplier': provider_info.get('code') if provider_info.get('type') == 'supplier' else None,
                        'customer_provided_client': provider_info.get('code') if provider_info.get('type') == 'customer_provided' else None,
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
        
        # Récupérer les informations du provider
        provider_info = materials[0].get('provider_info', {})
        provider_type = provider_info.get('type')
        
        # Définir les champs selon le type de provider
        if provider_type == 'customer_provided':
            # Pour les Customer Provided Items
            mr.customer = provider_info.get('code')
            mr.title = f"Material Request - Customer Provided: {provider_info.get('name')}"
            remarks_prefix = f"CUSTOMER PROVIDED - Client: {provider_info.get('name')}"
        elif provider_type == 'supplier':
            # Pour les Suppliers normaux
            if hasattr(mr, 'supplier'):  # Vérifier si le champ supplier existe
                mr.supplier = provider_info.get('code')
            mr.title = f"Material Request - Supplier: {provider_info.get('name')}"
            remarks_prefix = f"SUPPLIER - Fournisseur: {provider_info.get('name')}"
        else:
            # Aucun provider défini
            mr.title = f"Material Request - No Provider"
            remarks_prefix = "NO PROVIDER - Pas de fournisseur défini"
        
        # Ajouter une note explicative
        source_sales_orders = set()
        for material in materials:
            for source in material.get('source_items', []):
                source_sales_orders.add(source.get('sales_order'))
        
        mr.remarks = f"{remarks_prefix} | Sales Orders: {', '.join(source_sales_orders)} | Créé automatiquement"
        
        # Ajouter les items
        for material in materials:
            item_remarks = f"Manque: {material['shortage_qty']} | Provider: {provider_info.get('name', 'N/A')}"
            
            mr.append("items", {
                "item_code": material['item_code'],
                "item_name": material['item_name'],
                "qty": material['shortage_qty'],
                "uom": material['stock_uom'],
                "warehouse": get_default_warehouse_for_item(material['item_code']),
                "schedule_date": add_days(nowdate(), 7),
                "description": item_remarks
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


@frappe.whitelist()
def check_available_fields():
    """
    Vérifie quels champs sont disponibles dans les tables Item et Item Supplier
    """
    try:
        result = {}
        
        # Vérifier les colonnes de la table Item
        item_columns = frappe.db.sql("SHOW COLUMNS FROM `tabItem`", as_dict=True)
        result['item_columns'] = [col['Field'] for col in item_columns if 'customer' in col['Field'].lower() or 'provider' in col['Field'].lower()]
        
        # Vérifier les colonnes de la table Item Supplier
        supplier_columns = frappe.db.sql("SHOW COLUMNS FROM `tabItem Supplier`", as_dict=True)
        result['supplier_columns'] = [col['Field'] for col in supplier_columns]
        
        # Vérifier si la table Item Customer existe
        try:
            item_customer_exists = frappe.db.sql("SHOW TABLES LIKE 'tabItem Customer'")
            result['item_customer_exists'] = bool(item_customer_exists)
        except:
            result['item_customer_exists'] = False
            
        return result
        
    except Exception as e:
        return {'error': str(e)}


# ================== FONCTIONS D'EXPORT ET EMAIL ==================

@frappe.whitelist()
def generate_material_requirements_pdf(table_data, visible_columns, meta_info):
    """
    Génère un PDF du rapport des besoins en matières premières
    """
    try:
        if isinstance(table_data, str):
            table_data = json.loads(table_data)
        if isinstance(visible_columns, str):
            visible_columns = json.loads(visible_columns)
        if isinstance(meta_info, str):
            meta_info = json.loads(meta_info)
        
        # Générer le HTML pour le PDF
        html_content = generate_pdf_html_content(table_data, visible_columns, meta_info)
        
        # Créer le PDF en utilisant les fonctionnalités de Frappe
        from frappe.utils.pdf import get_pdf
        pdf_file = get_pdf(html_content)
        
        # Sauvegarder le fichier PDF
        file_name = f"besoins_matieres_premieres_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Créer le fichier avec le bon contenu
        import base64
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "content": base64.b64encode(pdf_file).decode(),
            "decode": True,
            "is_private": 0,
            "folder": "Home"
        })
        file_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "success": True,
            "file_url": file_doc.file_url,
            "file_name": file_name
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur génération PDF: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def send_material_requirements_email(recipients, subject, message, attach_pdf, table_data, visible_columns, meta_info):
    """
    Envoie le rapport par email
    """
    try:
        if isinstance(table_data, str):
            table_data = json.loads(table_data)
        if isinstance(visible_columns, str):
            visible_columns = json.loads(visible_columns)
        if isinstance(meta_info, str):
            meta_info = json.loads(meta_info)
        
        # Préparer la liste des destinataires
        recipient_list = [email.strip() for email in recipients.split(',')]
        
        # Générer le contenu HTML pour l'email
        html_content = generate_email_html_content(table_data, visible_columns, meta_info)
        
        attachments = []
        
        # Générer le PDF si demandé
        if cint(attach_pdf):
            pdf_result = generate_material_requirements_pdf(table_data, visible_columns, meta_info)
            if pdf_result.get('success'):
                # Lire le contenu du fichier PDF
                file_path = frappe.get_site_path() + pdf_result.get('file_url')
                with open(file_path, 'rb') as f:
                    pdf_content = f.read()
                
                attachments.append({
                    'fname': pdf_result.get('file_name'),
                    'fcontent': pdf_content
                })
        
        # Envoyer l'email
        frappe.sendmail(
            recipients=recipient_list,
            subject=subject,
            message=html_content,
            attachments=attachments,
            delayed=False
        )
        
        return {
            "success": True,
            "message": f"Email envoyé à {len(recipient_list)} destinataire(s)"
        }
        
    except Exception as e:
        frappe.log_error(f"Erreur envoi email: {str(e)}")
        return {"success": False, "error": str(e)}


def generate_pdf_html_content(table_data, visible_columns, meta_info):
    """
    Génère le contenu HTML pour le PDF
    """
    # En-tête du tableau
    headers_html = ""
    for col_key in visible_columns:
        if col_key in ['item-code', 'description', 'qty-required', 'stock-available', 'shortage', 'supplier', 'order-number', 'status']:
            col_config = {
                'item-code': 'Item Code',
                'description': 'Description', 
                'qty-required': 'Qty Requise',
                'stock-available': 'Stock Disponible',
                'shortage': 'Manque',
                'supplier': 'Fournisseur',
                'order-number': 'Order Number',
                'status': 'Statut'
            }
            headers_html += f"<th>{col_config.get(col_key, col_key)}</th>"
    
    # Corps du tableau
    rows_html = ""
    for row_data in table_data:
        row_type = row_data.get('_type', 'detail')
        row_class = 'detail-row' if row_type == 'detail' else 'total-row'
        
        rows_html += f'<tr class="{row_class}">'
        for col_key in visible_columns:
            if col_key in ['item-code', 'description', 'qty-required', 'stock-available', 'shortage', 'supplier', 'order-number', 'status']:
                col_config = {
                    'item-code': 'Item Code',
                    'description': 'Description',
                    'qty-required': 'Qty Requise', 
                    'stock-available': 'Stock Disponible',
                    'shortage': 'Manque',
                    'supplier': 'Fournisseur',
                    'order-number': 'Order Number',
                    'status': 'Statut'
                }
                cell_value = row_data.get(col_config.get(col_key, col_key), '')
                rows_html += f"<td>{cell_value}</td>"
        rows_html += '</tr>'
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Besoins en Matières Premières</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #2c3e50; text-align: center; margin-bottom: 30px; }}
            .meta-info {{ margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 11px; }}
            th, td {{ border: 1px solid #ddd; padding: 6px; text-align: left; }}
            th {{ background-color: #4a90e2; color: white; font-weight: bold; }}
            .detail-row {{ background-color: #fff; }}
            .total-row {{ background-color: #f0f0f0; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>📋 Rapport des Besoins en Matières Premières</h1>
        <div class="meta-info">
            <strong>Date de génération:</strong> {meta_info.get('generated_date', '')}<br>
            <strong>Heure:</strong> {meta_info.get('generated_time', '')}<br>
            <strong>Généré par:</strong> {meta_info.get('generated_by', '')}
        </div>
        <table>
            <thead>
                <tr>{headers_html}</tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </body>
    </html>
    """
    
    return html_content


def generate_email_html_content(table_data, visible_columns, meta_info):
    """
    Génère le contenu HTML pour l'email
    """
    # Utiliser la même logique que pour le PDF mais avec un style email-friendly
    headers_html = ""
    for col_key in visible_columns[:6]:  # Limiter les colonnes pour l'email
        if col_key in ['item-code', 'description', 'qty-required', 'shortage', 'supplier', 'status']:
            col_config = {
                'item-code': 'Item Code',
                'description': 'Description',
                'qty-required': 'Qty Requise', 
                'shortage': 'Manque',
                'supplier': 'Fournisseur',
                'status': 'Statut'
            }
            headers_html += f"<th style='background: #4a90e2; color: white; padding: 8px; border: 1px solid #ddd;'>{col_config.get(col_key, col_key)}</th>"
    
    # Limiter à 20 premières lignes pour l'email
    limited_data = table_data[:20] if len(table_data) > 20 else table_data
    
    rows_html = ""
    for row_data in limited_data:
        rows_html += '<tr>'
        for col_key in visible_columns[:6]:
            if col_key in ['item-code', 'description', 'qty-required', 'shortage', 'supplier', 'status']:
                col_config = {
                    'item-code': 'Item Code',
                    'description': 'Description',
                    'qty-required': 'Qty Requise',
                    'shortage': 'Manque', 
                    'supplier': 'Fournisseur',
                    'status': 'Statut'
                }
                cell_value = row_data.get(col_config.get(col_key, col_key), '')
                rows_html += f"<td style='padding: 8px; border: 1px solid #ddd;'>{cell_value}</td>"
        rows_html += '</tr>'
    
    if len(table_data) > 20:
        rows_html += f"<tr><td colspan='6' style='text-align: center; padding: 10px; font-style: italic;'>... et {len(table_data) - 20} lignes supplémentaires (voir PDF joint)</td></tr>"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif;">
        <h2 style="color: #2c3e50;">📋 Rapport des Besoins en Matières Premières</h2>
        
        <div style="background: #f8f9fa; padding: 15px; margin-bottom: 20px; border-radius: 5px;">
            <strong>Date de génération:</strong> {meta_info.get('generated_date', '')}<br>
            <strong>Heure:</strong> {meta_info.get('generated_time', '')}<br>
            <strong>Généré par:</strong> {meta_info.get('generated_by', '')}
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
            <thead>
                <tr>{headers_html}</tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        
        <p style="margin-top: 20px; color: #666; font-size: 12px;">
            Ce rapport a été généré automatiquement par le système ERP.
        </p>
    </div>
    """
    
    return html_content