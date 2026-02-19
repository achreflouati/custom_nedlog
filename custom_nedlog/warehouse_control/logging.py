import frappe
from typing import Optional, Dict, Any

def log_warehouse_event(
    warehouse: str,
    event_type: str,
    transaction_type: str,
    transaction_name: str,
    prev_customer: Optional[str] = None,
    new_customer: Optional[str] = None,
    qty_before: float = 0.0,
    qty_after: float = 0.0,
    user: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Log warehouse control event
    
    Args:
        warehouse: Warehouse name
        event_type: Assignment/Warning/Release
        transaction_type: Document type (Purchase Receipt, etc.)
        transaction_name: Document name
        prev_customer: Previous assigned customer
        new_customer: New assigned customer
        qty_before: Quantity before transaction
        qty_after: Quantity after transaction
        user: User performing action
        additional_data: Extra data to log
        
    Returns:
        Success status
    """
    try:
        if not user:
            user = frappe.session.user
            
        log_doc = frappe.get_doc({
            "doctype": "Warehouse Control Log",
            "warehouse": warehouse,
            "previous_customer": prev_customer,
            "new_customer": new_customer,
            "transaction_type": transaction_type,
            "transaction_name": transaction_name,
            "event_type": event_type,
            "total_qty_before": float(qty_before),
            "total_qty_after": float(qty_after),
            "user": user,
            "timestamp": frappe.utils.now()
        })
        
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()  # Ensure log is saved immediately
        
        return True
        
    except Exception as e:
        frappe.log_error(
            f"Failed to log warehouse event: {str(e)}\n"
            f"Warehouse: {warehouse}, Event: {event_type}, Transaction: {transaction_name}",
            "Warehouse Control Logging"
        )
        return False

def log_assignment(warehouse: str, customer: str, transaction_type: str, transaction_name: str, qty_before: float, qty_after: float) -> bool:
    """
    Log warehouse assignment event
    """
    return log_warehouse_event(
        warehouse=warehouse,
        event_type="Assignment",
        transaction_type=transaction_type,
        transaction_name=transaction_name,
        prev_customer=None,
        new_customer=customer,
        qty_before=qty_before,
        qty_after=qty_after
    )

def log_warning(warehouse: str, assigned_customer: str, attempting_customer: str, transaction_type: str, transaction_name: str, qty_before: float) -> bool:
    """
    Log warehouse mixing warning event
    """
    return log_warehouse_event(
        warehouse=warehouse,
        event_type="Warning",
        transaction_type=transaction_type,
        transaction_name=transaction_name,
        prev_customer=assigned_customer,
        new_customer=attempting_customer,
        qty_before=qty_before,
        qty_after=qty_before  # No quantity change in warning
    )

def log_release(warehouse: str, released_customer: str, transaction_type: str, transaction_name: str, qty_before: float) -> bool:
    """
    Log warehouse release event
    """
    return log_warehouse_event(
        warehouse=warehouse,
        event_type="Release",
        transaction_type=transaction_type,
        transaction_name=transaction_name,
        prev_customer=released_customer,
        new_customer=None,
        qty_before=qty_before,
        qty_after=0.0
    )
