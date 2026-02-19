import frappe
from typing import List, Dict, Any

def get_warehouse_customer_status_data(filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Get data for Warehouse Customer Status Report
    
    Args:
        filters: Report filters
        
    Returns:
        Report data list
    """
    conditions = []
    values = []
    
    if filters:
        if filters.get("warehouse"):
            conditions.append("w.name = %s")
            values.append(filters["warehouse"])
            
        if filters.get("assigned_customer"):
            conditions.append("w.assigned_customer = %s")
            values.append(filters["assigned_customer"])
            
        if filters.get("warehouse_status"):
            conditions.append("w.warehouse_status = %s")
            values.append(filters["warehouse_status"])
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT 
            w.name as warehouse,
            w.assigned_customer,
            w.warehouse_status,
            COALESCE(SUM(b.actual_qty), 0) as total_quantity,
            w.last_assignment_date,
            (
                SELECT MAX(sle.posting_date) 
                FROM `tabStock Ledger Entry` sle 
                WHERE sle.warehouse = w.name 
                AND sle.is_cancelled = 0 
                AND sle.docstatus = 1
            ) as last_movement_date,
            w.control_mode,
            w.company
        FROM 
            `tabWarehouse` w
        LEFT JOIN 
            `tabBin` b ON b.warehouse = w.name
        WHERE 
            {where_clause}
            AND w.is_group = 0
        GROUP BY 
            w.name
        ORDER BY 
            w.name
    """
    
    return frappe.db.sql(query, values, as_dict=1)

def get_warehouse_activity_summary(warehouse: str, days: int = 30) -> Dict[str, Any]:
    """
    Get warehouse activity summary for dashboard
    
    Args:
        warehouse: Warehouse name
        days: Number of days to analyze
        
    Returns:
        Activity summary
    """
    from_date = frappe.utils.add_days(frappe.utils.nowdate(), -days)
    
    # Get control log events
    events = frappe.db.sql("""
        SELECT 
            event_type,
            COUNT(*) as count,
            MAX(timestamp) as last_event
        FROM 
            `tabWarehouse Control Log`
        WHERE 
            warehouse = %s
            AND DATE(timestamp) >= %s
        GROUP BY 
            event_type
    """, (warehouse, from_date), as_dict=1)
    
    # Get stock movements
    movements = frappe.db.sql("""
        SELECT 
            COUNT(*) as movement_count,
            SUM(ABS(actual_qty)) as total_qty_moved
        FROM 
            `tabStock Ledger Entry`
        WHERE 
            warehouse = %s
            AND posting_date >= %s
            AND is_cancelled = 0
            AND docstatus = 1
    """, (warehouse, from_date), as_dict=1)
    
    return {
        "warehouse": warehouse,
        "period_days": days,
        "events": {event["event_type"]: event for event in events},
        "movements": movements[0] if movements else {"movement_count": 0, "total_qty_moved": 0}
    }