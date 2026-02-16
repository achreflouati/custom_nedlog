# -*- coding: utf-8 -*-
# Copyright (c) 2024, achref louati and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

@frappe.whitelist()
def get_sales_order_bom_info(sales_order):
    """
    Récupérer les informations BOM pour une Sales Order donnée
    """
    try:
        # Récupérer la Sales Order
        so_doc = frappe.get_doc("Sales Order", sales_order)
        
        bom_info = []
        
        for item in so_doc.items:
            # Chercher le BOM actif et par défaut pour l'item
            bom_list = frappe.get_list("BOM", 
                filters={
                    "item": item.item_code,
                    "is_active": 1,
                    "is_default": 1
                },
                fields=["name", "item", "quantity"]
            )
            
            item_info = {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
                "delivery_date": item.delivery_date,
                "has_bom": False,
                "bom_name": None,
                "raw_materials": []
            }
            
            if bom_list:
                bom = frappe.get_doc("BOM", bom_list[0].name)
                item_info["has_bom"] = True
                item_info["bom_name"] = bom.name
                
                # Récupérer les matières premières
                for bom_item in bom.items:
                    # Récupérer les informations de stock
                    stock_info = frappe.get_list("Bin",
                        filters={"item_code": bom_item.item_code},
                        fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty"]
                    )
                    
                    total_available = sum([bin_info.actual_qty or 0 for bin_info in stock_info])
                    
                    raw_material = {
                        "item_code": bom_item.item_code,
                        "item_name": bom_item.item_name,
                        "qty_per_unit": bom_item.qty,
                        "total_qty": bom_item.qty * item.qty,
                        "uom": bom_item.uom,
                        "rate": bom_item.rate or 0,
                        "amount": (bom_item.rate or 0) * (bom_item.qty * item.qty),
                        "stock_info": stock_info,
                        "total_available": total_available
                    }
                    
                    item_info["raw_materials"].append(raw_material)
            
            bom_info.append(item_info)
        
        return {
            "success": True,
            "sales_order": sales_order,
            "customer": so_doc.customer,
            "bom_info": bom_info
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Erreur get_sales_order_bom_info")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_multiple_sales_orders_bom_info(sales_orders):
    """
    Récupérer les informations BOM pour plusieurs Sales Orders
    """
    try:
        if isinstance(sales_orders, str):
            import json
            sales_orders = json.loads(sales_orders)
        
        all_bom_info = []
        total_raw_materials = {}
        
        for so_name in sales_orders:
            so_info = get_sales_order_bom_info(so_name)
            if so_info["success"]:
                all_bom_info.append(so_info)
                
                # Accumuler les matières premières
                for item in so_info["bom_info"]:
                    if item["has_bom"]:
                        for material in item["raw_materials"]:
                            item_code = material["item_code"]
                            if item_code not in total_raw_materials:
                                total_raw_materials[item_code] = {
                                    "item_name": material["item_name"],
                                    "total_needed": 0,
                                    "total_available": material["total_available"],
                                    "uom": material["uom"],
                                    "stock_info": material["stock_info"]
                                }
                            total_raw_materials[item_code]["total_needed"] += material["total_qty"]
        
        return {
            "success": True,
            "sales_orders": sales_orders,
            "all_bom_info": all_bom_info,
            "total_raw_materials": total_raw_materials
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Erreur get_multiple_sales_orders_bom_info")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_item_stock_levels(item_code):
    """
    Récupérer les niveaux de stock pour un item donné
    """
    try:
        stock_info = frappe.get_list("Bin",
            filters={"item_code": item_code},
            fields=["warehouse", "actual_qty", "reserved_qty", "projected_qty", "planned_qty"]
        )
        
        # Récupérer aussi les informations de l'item
        item_info = frappe.get_doc("Item", item_code)
        
        return {
            "success": True,
            "item_code": item_code,
            "item_name": item_info.item_name,
            "stock_uom": item_info.stock_uom,
            "stock_info": stock_info,
            "total_available": sum([bin_info.actual_qty or 0 for bin_info in stock_info])
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Erreur get_item_stock_levels")
        return {
            "success": False,
            "error": str(e)
        }