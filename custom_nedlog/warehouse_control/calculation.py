import frappe
from typing import Optional, Dict, Any

def get_total_qty(warehouse: str) -> float:
    """
    Calculate total quantity in warehouse using Bin table (preferred) or SLE fallback
    
    Args:
        warehouse: Warehouse name
        
    Returns:
        Total actual quantity in warehouse
    """
    if not warehouse:
        return 0.0
        
    try:
        # Primary method: Use Bin table for performance
        bins = frappe.get_all(
            "Bin", 
            filters={"warehouse": warehouse}, 
            fields=["actual_qty"],
            pluck="actual_qty"
        )
        
        if bins:
            return sum(bins)
        
        # Fallback: Calculate from Stock Ledger Entry
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(actual_qty), 0) as total_qty 
            FROM `tabStock Ledger Entry` 
            WHERE warehouse = %s 
            AND is_cancelled = 0 
            AND docstatus = 1
        """, (warehouse,), as_dict=1)
        
        return float(result[0]["total_qty"]) if result else 0.0
        
    except Exception as e:
        frappe.log_error(f"Error calculating total qty for warehouse {warehouse}: {str(e)}", "Warehouse Control")
        return 0.0

def get_warehouse_summary(warehouse: str) -> Dict[str, Any]:
    """
    Get comprehensive warehouse information
    
    Args:
        warehouse: Warehouse name
        
    Returns:
        Dictionary with warehouse details
    """
    try:
        warehouse_doc = frappe.get_doc("Warehouse", warehouse)
        total_qty = get_total_qty(warehouse)
        
        return {
            "warehouse": warehouse,
            "total_qty": total_qty,
            "assigned_customer": getattr(warehouse_doc, "assigned_customer", None),
            "warehouse_status": getattr(warehouse_doc, "warehouse_status", "Available"),
            "last_assignment_date": getattr(warehouse_doc, "last_assignment_date", None),
            "control_mode": getattr(warehouse_doc, "control_mode", "Warning"),
            "is_reserved": total_qty != 0
        }
    except Exception as e:
        frappe.log_error(f"Error getting warehouse summary for {warehouse}: {str(e)}", "Warehouse Control")
        return {"warehouse": warehouse, "error": True}
