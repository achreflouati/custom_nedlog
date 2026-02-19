import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
    fields = [
        {
            "fieldname": "assigned_customer",
            "label": "Assigned Customer",
            "fieldtype": "Link",
            "options": "Customer",
            "read_only": 1,
            "insert_after": "warehouse_name",
        },
        {
            "fieldname": "warehouse_status",
            "label": "Warehouse Status",
            "fieldtype": "Select",
            "options": "Available\nReserved",
            "read_only": 1,
            "insert_after": "assigned_customer",
        },
        {
            "fieldname": "last_assignment_date",
            "label": "Last Assignment Date",
            "fieldtype": "Datetime",
            "read_only": 1,
            "insert_after": "warehouse_status",
        },
        {
            "fieldname": "control_mode",
            "label": "Control Mode",
            "fieldtype": "Select",
            "options": "Disabled\nWarning\nStrict",
            "default": "Warning",
            "read_only": 1,
            "insert_after": "last_assignment_date",
        },
    ]
    for field in fields:
        create_custom_field("Warehouse", field)
