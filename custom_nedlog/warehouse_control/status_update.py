import frappe
from typing import Optional
from datetime import datetime

def update_warehouse_status(
    warehouse: str, 
    customer: Optional[str] = None, 
    status: Optional[str] = None, 
    assignment_date: Optional[datetime] = None,
    commit: bool = True
) -> bool:
    """
    Update warehouse control fields
    
    Args:
        warehouse: Warehouse name
        customer: Customer to assign (None to clear)
        status: Warehouse status (Available/Reserved)
        assignment_date: Assignment timestamp
        commit: Whether to commit changes immediately
        
    Returns:
        Success status
    """
    try:
        if not frappe.db.exists("Warehouse", warehouse):
            frappe.log_error(f"Warehouse {warehouse} does not exist", "Warehouse Control")
            return False
            
        # Prepare update dict
        update_dict = {}
        
        if customer is not None:
            update_dict["assigned_customer"] = customer
            
        if status is not None:
            if status not in ["Available", "Reserved"]:
                frappe.log_error(f"Invalid warehouse status: {status}", "Warehouse Control")
                return False
            update_dict["warehouse_status"] = status
            
        if assignment_date is not None:
            update_dict["last_assignment_date"] = assignment_date
            
        if not update_dict:
            return True  # Nothing to update
            
        # Perform batch update for efficiency
        frappe.db.set_value("Warehouse", warehouse, update_dict)
        
        if commit:
            frappe.db.commit()
            
        return True
        
    except Exception as e:
        frappe.log_error(f"Error updating warehouse {warehouse}: {str(e)}", "Warehouse Control")
        return False

def assign_warehouse_to_customer(warehouse: str, customer: str) -> bool:
    """
    Assign warehouse to customer with full status update
    
    Args:
        warehouse: Warehouse name
        customer: Customer name
        
    Returns:
        Success status
    """
    return update_warehouse_status(
        warehouse=warehouse,
        customer=customer,
        status="Reserved",
        assignment_date=frappe.utils.now()
    )

def release_warehouse(warehouse: str) -> bool:
    """
    Release warehouse (make available)
    
    Args:
        warehouse: Warehouse name
        
    Returns:
        Success status
    """
    return update_warehouse_status(
        warehouse=warehouse,
        customer=None,
        status="Available",
        assignment_date=None
    )
