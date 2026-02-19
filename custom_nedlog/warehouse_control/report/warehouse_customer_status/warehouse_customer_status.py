import frappe
from custom_nedlog.warehouse_control.reporting import get_warehouse_customer_status_data

def execute(filters=None):
	"""
	Execute Warehouse Customer Status Report
	
	Args:
		filters: Report filters
		
	Returns:
		Tuple of (columns, data)
	"""
	columns = [
		{
			"label": "Warehouse",
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 200
		},
		{
			"label": "Assigned Customer",
			"fieldname": "assigned_customer",
			"fieldtype": "Link", 
			"options": "Customer",
			"width": 200
		},
		{
			"label": "Status",
			"fieldname": "warehouse_status",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": "Total Quantity",
			"fieldname": "total_quantity",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": "Last Assignment",
			"fieldname": "last_assignment_date",
			"fieldtype": "Datetime",
			"width": 140
		},
		{
			"label": "Last Movement",
			"fieldname": "last_movement_date",
			"fieldtype": "Date",
			"width": 120
		}
	]
	
	data = get_warehouse_customer_status_data(filters)
	
	return columns, data