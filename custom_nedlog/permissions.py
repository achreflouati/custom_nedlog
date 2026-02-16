# -*- coding: utf-8 -*-
# Permissions pour les API de production_analysis

from frappe import _

def get_permission_query_conditions(user):
    """
    Conditions de permission pour les requêtes
    """
    if not user:
        user = frappe.session.user
    
    # Les utilisateurs avec les rôles Manufacturing Manager ou Stock Manager peuvent accéder
    if "Manufacturing Manager" in frappe.get_roles(user) or "Stock Manager" in frappe.get_roles(user):
        return ""
    
    # Les autres utilisateurs ne peuvent accéder qu'aux données de leur société
    return """(`tabSales Order`.company in (select company from `tabUser Permission` 
                where allow='Company' and for_value='{user}' and user='{user}'))""".format(user=user)


def has_permission(doc, user):
    """
    Vérifie si l'utilisateur a les permissions nécessaires
    """
    if not user:
        user = frappe.session.user
    
    # Super utilisateur a toujours accès
    if user == "Administrator":
        return True
    
    # Vérifier les rôles nécessaires
    user_roles = frappe.get_roles(user)
    required_roles = ["Manufacturing Manager", "Stock Manager", "Sales Manager", "Purchase Manager"]
    
    return any(role in user_roles for role in required_roles)