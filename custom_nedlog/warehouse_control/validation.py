import frappe
from typing import Optional, Dict, Any, List, Tuple
from .calculation import get_total_qty, get_warehouse_summary
from .status_update import assign_warehouse_to_customer, release_warehouse
from .logging import log_assignment, log_warning, log_release

def get_customer_from_transaction(doc: Dict[str, Any], item: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Extract customer from various transaction types
    
    Args:
        doc: Transaction document
        item: Item row (for Stock Entry)
        
    Returns:
        Customer name or None
    """
    doctype = doc.get("doctype")
    
    # Purchase Receipt: Use supplier as customer (business requirement)
    if doctype == "Purchase Receipt" and doc.get("supplier"):
        return doc["supplier"]
    
    # Direct customer field (Delivery Note, Material Request, Sales Order)
    if doc.get("customer"):
        return doc["customer"]
    
    # Stock Entry: Infer from linked documents
    if doctype == "Stock Entry" and item:
        # Try Sales Order
        if item.get("sales_order"):
            return frappe.db.get_value("Sales Order", item["sales_order"], "customer")
        
        # Try Delivery Note
        if item.get("delivery_note"):
            return frappe.db.get_value("Delivery Note", item["delivery_note"], "customer")
        
        # Try Material Request
        if item.get("material_request"):
            return frappe.db.get_value("Material Request", item["material_request"], "customer")
    
    return None

def get_warehouse_from_item(item: Dict[str, Any], transaction_type: str) -> Optional[str]:
    """
    Extract warehouse from item based on transaction type
    
    Args:
        item: Item dictionary
        transaction_type: 'incoming' or 'outgoing'
        
    Returns:
        Warehouse name or None
    """
    if transaction_type == "incoming":
        # For incoming: t_warehouse (Stock Entry) or warehouse (Purchase Receipt)
        return item.get("t_warehouse") or item.get("warehouse")
    else:
        # For outgoing: s_warehouse (Stock Entry) or warehouse (Delivery Note)
        return item.get("s_warehouse") or item.get("warehouse")

def show_warning_message(warehouse: str, assigned_customer: str, attempting_customer: str) -> None:
    """
    Display non-blocking warning message
    """
    message = (
        f"⚠️ Warehouse <strong>{warehouse}</strong> is currently assigned to "
        f"<strong>{assigned_customer}</strong> and contains stock.<br>"
        f"Attempting to use for <strong>{attempting_customer}</strong> may cause inconsistencies."
    )
    
    frappe.msgprint(
        message,
        title="Warehouse Customer Mixing Warning",
        indicator="orange",
        alert=True
    )

def is_control_enabled(warehouse: str) -> bool:
    """
    Check if warehouse control is enabled for this warehouse
    """
    try:
        control_mode = frappe.db.get_value("Warehouse", warehouse, "control_mode")
        return control_mode in ["Warning", "Strict"]  # Future: Strict mode
    except:
        return True  # Default to enabled

def validate_warehouse_assignment(
    warehouse: str, 
    customer: str, 
    transaction_doc: Dict[str, Any], 
    is_incoming: bool = True
) -> Dict[str, Any]:
    """
    Core warehouse validation logic
    
    Args:
        warehouse: Warehouse name
        customer: Customer attempting to use warehouse
        transaction_doc: Transaction document
        is_incoming: True for incoming transactions
        
    Returns:
        Validation result dictionary
    """
    if not warehouse or not customer:
        return {"action": "skip", "reason": "Missing warehouse or customer"}
    
    if not is_control_enabled(warehouse):
        return {"action": "allow", "reason": "Control disabled"}
    
    try:
        warehouse_info = get_warehouse_summary(warehouse)
        
        if warehouse_info.get("error"):
            return {"action": "skip", "reason": "Warehouse info error"}
        
        total_qty = warehouse_info["total_qty"]
        assigned_customer = warehouse_info["assigned_customer"]
        
        result = {
            "warehouse": warehouse,
            "customer": customer,
            "total_qty_before": total_qty,
            "assigned_customer": assigned_customer,
            "transaction_type": transaction_doc.get("doctype"),
            "transaction_name": transaction_doc.get("name")
        }
        
        if is_incoming:
            # Incoming transaction logic
            if total_qty == 0:
                # Warehouse is empty - assign to customer
                result.update({
                    "action": "assign",
                    "reason": "Warehouse empty - assigning to customer"
                })
            elif assigned_customer == customer:
                # Same customer - allow silently
                result.update({
                    "action": "allow", 
                    "reason": "Same customer"
                })
            elif assigned_customer is None and total_qty != 0:
                # Inconsistent state: has stock but no assigned customer - auto-assign
                result.update({
                    "action": "assign",
                    "reason": "Warehouse has stock but no assigned customer - auto-assigning"
                })
            else:
                # Different customer - show warning
                result.update({
                    "action": "warn",
                    "reason": f"Warehouse assigned to {assigned_customer}, attempting {customer}"
                })
        else:
            # Outgoing transaction logic - just track for potential release
            result.update({
                "action": "track",
                "reason": "Outgoing transaction"
            })
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Validation error for warehouse {warehouse}: {str(e)}", "Warehouse Control")
        return {"action": "skip", "reason": f"Validation error: {str(e)}"}

def handle_incoming_transaction(doc, method):
    """
    Handle incoming transactions (Purchase Receipt, Stock Entry Material Receipt)
    """
    frappe.logger().info(f"Warehouse Control: Processing incoming {doc.doctype} - {doc.name}")
    
    try:
        for item in doc.get("items", []):
            warehouse = get_warehouse_from_item(item.__dict__, "incoming")
            if not warehouse:
                continue
            
            customer = get_customer_from_transaction(doc.__dict__, item.__dict__)
            if not customer:
                continue
            
            # Validate warehouse assignment
            validation_result = validate_warehouse_assignment(
                warehouse=warehouse,
                customer=customer,
                transaction_doc=doc.__dict__,
                is_incoming=True
            )
            
            action = validation_result.get("action")
            
            if action == "assign":
                # Assign warehouse to customer
                if assign_warehouse_to_customer(warehouse, customer):
                    log_assignment(
                        warehouse=warehouse,
                        customer=customer,
                        transaction_type=doc.doctype,
                        transaction_name=doc.name,
                        qty_before=validation_result["total_qty_before"],
                        qty_after=get_total_qty(warehouse)  # Recalculate after transaction
                    )
                    frappe.logger().info(f"Warehouse {warehouse} assigned to {customer}")
                    
            elif action == "warn":
                # Show warning and log
                show_warning_message(
                    warehouse=warehouse,
                    assigned_customer=validation_result["assigned_customer"],
                    attempting_customer=customer
                )
                log_warning(
                    warehouse=warehouse,
                    assigned_customer=validation_result["assigned_customer"],
                    attempting_customer=customer,
                    transaction_type=doc.doctype,
                    transaction_name=doc.name,
                    qty_before=validation_result["total_qty_before"]
                )
                frappe.logger().info(f"Warehouse mixing warning: {warehouse}")
                
            elif action == "allow":
                frappe.logger().info(f"Warehouse {warehouse} usage allowed for {customer}")
                
    except Exception as e:
        frappe.log_error(f"Error in incoming transaction handler: {str(e)}", "Warehouse Control")

def handle_outgoing_transaction(doc, method):
    """
    Handle outgoing transactions (Delivery Note, Stock Entry Material Issue)
    """
    frappe.logger().info(f"Warehouse Control: Processing outgoing {doc.doctype} - {doc.name}")
    
    try:
        for item in doc.get("items", []):
            warehouse = get_warehouse_from_item(item.__dict__, "outgoing")
            if not warehouse:
                continue
            
            if not is_control_enabled(warehouse):
                continue
            
            # Check if warehouse should be released
            warehouse_info = get_warehouse_summary(warehouse)
            
            if warehouse_info.get("error"):
                continue
            
            total_qty_before = warehouse_info["total_qty"]
            assigned_customer = warehouse_info["assigned_customer"]
            
            # Recalculate after transaction
            total_qty_after = get_total_qty(warehouse)
            
            if total_qty_after == 0 and assigned_customer:
                # Release warehouse
                if release_warehouse(warehouse):
                    log_release(
                        warehouse=warehouse,
                        released_customer=assigned_customer,
                        transaction_type=doc.doctype,
                        transaction_name=doc.name,
                        qty_before=total_qty_before
                    )
                    frappe.logger().info(f"Warehouse {warehouse} released from {assigned_customer}")
                    
    except Exception as e:
        frappe.log_error(f"Error in outgoing transaction handler: {str(e)}", "Warehouse Control")
