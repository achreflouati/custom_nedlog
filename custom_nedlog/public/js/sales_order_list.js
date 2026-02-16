frappe.listview_settings['Sales Order'] = {
    refresh: function(listview) {
        // Nettoyer pour éviter les doublons lors du changement de filtre/page
        listview.page.remove_inner_button(__('Analyse le besoin'));
        listview.page.remove_inner_button(__('Créer Material Request'));

        // Bouton "Analyse le besoin"
        listview.page.add_inner_button(__('Analyse le besoin'), () => {
            let selected_docs = listview.get_checked_items();
            if (selected_docs.length === 0) {
                frappe.msgprint(__('Veuillez sélectionner au moins une Sales Order'));
                return;
            }
            
            let sales_order_names = selected_docs.map(d => d.name);
            analyze_production_requirements(sales_order_names);
        });

        // Bouton "Créer Material Request"
        listview.page.add_inner_button(__('Créer Material Request'), () => {
            let selected_docs = listview.get_checked_items();
            if (selected_docs.length === 0) {
                frappe.msgprint(__('Veuillez sélectionner au moins une Sales Order'));
                return;
            }
            
            let sales_order_names = selected_docs.map(d => d.name);
            create_material_requests_from_sales_orders(sales_order_names);
        });
    }
};

// ================== FONCTIONS PRINCIPALES ==================

/**
 * Analyse complète des besoins de production pour les Sales Orders sélectionnées
 */
function analyze_production_requirements(sales_order_names) {
    console.log('Starting production analysis for:', sales_order_names);
    
    let analysis_dialog = new frappe.ui.Dialog({
        title: `🔍 Analyse des Besoins de Production - ${sales_order_names.length} commande(s)`,
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'analysis_content',
                options: '<div class="text-center"><p>Chargement de l\'analyse...</p></div>'
            }
        ],
        size: 'extra-large'
        
    });
    
    analysis_dialog.show();
    
    // Étape 1: Récupérer les Sales Orders avec leurs items
    console.log("etape1")
    get_sales_orders_with_items(sales_order_names)
        .then(sales_orders_data => {
            // Étape 2: Analyser les BOMs et consolider les items
            console.log('Sales Orders data retrieved:', sales_orders_data);
            return analyze_bom_requirements(sales_orders_data);
        })
        .then(consolidated_data => {
            // Étape 3: Calculer les besoins en stock
            return calculate_stock_requirements(consolidated_data);
        })
        .then(final_analysis => {
            // Étape 4: Afficher les résultats
            display_production_analysis_results(analysis_dialog, final_analysis);
        })
        .catch(error => {
            console.error('Error in production analysis:', error);
            analysis_dialog.fields_dict.analysis_content.$wrapper.html(`
                <div class="alert alert-danger">
                    <h6><i class="fa fa-exclamation-triangle"></i> Erreur d'Analyse</h6>
                    <p>${error.message || 'Erreur inconnue lors de l\'analyse'}</p>
                </div>
            `);
        });
}

/**
 * Crée les Material Requests basées sur l'analyse des Sales Orders
 */
function create_material_requests_from_sales_orders(sales_order_names) {
    console.log('Creating Material Requests for:', sales_order_names);
    
    let mr_dialog = new frappe.ui.Dialog({
        title: `📋 Création Material Requests - ${sales_order_names.length} commande(s)`,
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'mr_content',
                options: '<div class="text-center"><p>Analyse et création des Material Requests...</p></div>'
            }
        ],
        size: 'large'
    });
    
    mr_dialog.show();
    
    // Analyser d'abord les besoins
    get_sales_orders_with_items(sales_order_names)
        .then(sales_orders_data => analyze_bom_requirements(sales_orders_data))
        .then(consolidated_data => calculate_stock_requirements(consolidated_data))
        .then(analysis_data => {
            // Créer les Material Requests
            return create_grouped_material_requests(analysis_data);
        })
        .then(created_mrs => {
            display_material_request_results(mr_dialog, created_mrs);
        })
        .catch(error => {
            console.error('Error creating Material Requests:', error);
            mr_dialog.fields_dict.mr_content.$wrapper.html(`
                <div class="alert alert-danger">
                    <h6><i class="fa fa-exclamation-triangle"></i> Erreur</h6>
                    <p>${error.message || 'Erreur lors de la création des Material Requests'}</p>
                </div>
            `);
        });
}

// ================== FONCTIONS DE RÉCUPÉRATION DES DONNÉES ==================

/**
 * Récupère les Sales Orders avec leurs items
 */
function get_sales_orders_with_items(sales_order_names) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'custom_nedlog.production_analysis.get_sales_orders_with_items',
            args: {
                sales_order_names: sales_order_names
            },
            callback: function(response) {
                if (response.message) {
                    resolve(response.message);
                } else {
                    reject(new Error('Aucune donnée retournée pour les Sales Orders'));
                }
            },
            error: function(error) {
                reject(error);
            }
        });
    });
}

// ================== FONCTIONS D'ANALYSE BOM ==================

/**
 * Analyse les BOMs et consolide les items
 */
function analyze_bom_requirements(sales_orders_data) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'custom_nedlog.production_analysis.analyze_bom_requirements',
            args: {
                sales_orders_data: sales_orders_data
            },
            callback: function(response) {
                console.log('BOM analysis response:', response);
                if (response.message) {
                    resolve(response.message);
                } else {
                    reject(new Error('Erreur lors de l\'analyse des BOMs'));
                }
            },
            error: function(error) {
                reject(error);
            }
        });
    });
}

// ================== FONCTIONS DE CALCUL DES BESOINS ==================

/**
 * Calcule les besoins en stock et les disponibilités
 */
function calculate_stock_requirements(consolidated_data) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'custom_nedlog.production_analysis.calculate_stock_requirements',
            args: {
                consolidated_data: consolidated_data
            },
            callback: function(response) {
                if (response.message) {
                    resolve(response.message);
                } else {
                    reject(new Error('Erreur lors du calcul des besoins en stock'));
                }
            },
            error: function(error) {
                reject(error);
            }
        });
    });
}

// ================== FONCTIONS DE CRÉATION MATERIAL REQUEST ==================

/**
 * Crée les Material Requests groupées par fournisseur et entrepôt
 */
function create_grouped_material_requests(analysis_data) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: 'custom_nedlog.production_analysis.create_grouped_material_requests',
            args: {
                analysis_data: analysis_data
            },
            callback: function(response) {
                if (response.message) {
                    resolve(response.message);
                } else {
                    reject(new Error('Erreur lors de la création des Material Requests'));
                }
            },
            error: function(error) {
                reject(error);
            }
        });
    });
}

// ================== FONCTIONS D'AFFICHAGE ==================

/**
 * Affiche les résultats de l'analyse de production
 */
function display_production_analysis_results(dialog, analysis_data) {
    const html_content = generate_analysis_html(analysis_data);
    dialog.fields_dict.analysis_content.$wrapper.html(html_content);
}

/**
 * Affiche les résultats de création des Material Requests
 */
function display_material_request_results(dialog, created_mrs) {
    const html_content = generate_material_request_html(created_mrs);
    dialog.fields_dict.mr_content.$wrapper.html(html_content);
}

/**
 * Génère le HTML pour l'affichage de l'analyse
 */
function generate_analysis_html(analysis_data) {
    return `
        <div style="padding: 20px; font-family: 'Segoe UI', sans-serif;">
            <style>
                .analysis-stats {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin-bottom: 25px;
                }
                .stat-card {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                }
                .stat-number {
                    font-size: 2em;
                    font-weight: bold;
                    margin-bottom: 5px;
                }
                .stat-label {
                    font-size: 0.9em;
                    opacity: 0.9;
                }
                .analysis-section {
                    margin: 20px 0;
                }
                .section-title {
                    color: #2c3e50;
                    font-weight: 600;
                    margin: 25px 0 15px 0;
                    padding-bottom: 8px;
                    border-bottom: 2px solid #3498db;
                }
                .data-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .data-table thead {
                    background: linear-gradient(135deg, #4a90e2 0%, #357abd 100%);
                    color: white;
                }
                .data-table th, .data-table td {
                    padding: 12px 8px;
                    text-align: left;
                    border-bottom: 1px solid #eee;
                }
                .data-table th {
                    font-weight: 600;
                    text-transform: uppercase;
                    font-size: 11px;
                    letter-spacing: 0.5px;
                }
                .data-table tbody tr:hover {
                    background-color: #f8f9fa;
                }
                .shortage-row {
                    background-color: #ffebee !important;
                }
                .available-row {
                    background-color: #e8f5e8 !important;
                }
            </style>
            
            <div class="analysis-stats">
                <div class="stat-card">
                    <div class="stat-number">${analysis_data.stats?.total_sales_orders || 0}</div>
                    <div class="stat-label">Sales Orders</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${analysis_data.stats?.total_finished_goods || 0}</div>
                    <div class="stat-label">Produits Finis</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${analysis_data.stats?.total_raw_materials || 0}</div>
                    <div class="stat-label">Matières Premières</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${analysis_data.stats?.items_with_shortage || 0}</div>
                    <div class="stat-label">Items en Rupture</div>
                </div>
            </div>
            
            <h3 class="section-title">📦 Consolidation des Items Finis</h3>
            <div class="analysis-section">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Item Code</th>
                            <th>Description</th>
                            <th>Qty Totale</th>
                            <th>BOM</th>
                            <th>Entrepôt</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${generate_consolidated_items_rows(analysis_data.consolidated_items)}
                    </tbody>
                </table>
            </div>
            
            <h3 class="section-title">🔧 Besoins en Matières Premières</h3>
            <div class="analysis-section">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Item Code</th>
                            <th>Description</th>
                            <th>Qty Requise</th>
                            <th>Stock Disponible</th>
                            <th>Manque</th>
                            <th>Fournisseur</th>
                            <th>Order Number</th>
                            <th>Statut</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${generate_raw_materials_rows(analysis_data.raw_materials_requirements)}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

/**
 * Génère le HTML pour les Material Requests créées
 */
function generate_material_request_html(created_mrs) {
    return `
        <div style="padding: 20px;">
            <div class="alert alert-success">
                <h6><i class="fa fa-check-circle"></i> Material Requests Créées</h6>
                <p>${created_mrs.length} Material Request(s) ont été créée(s) avec succès.</p>
            </div>
            
            <div class="table-responsive">
                <table class="table table-bordered">
                    <thead class="thead-light">
                        <tr>
                            <th>Material Request</th>
                            <th>Type</th>
                            <th>Fournisseur</th>
                            <th>Entrepôt</th>
                            <th>Nb Items</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${created_mrs.map(mr => `
                            <tr>
                                <td><a href="/app/material-request/${mr.name}" target="_blank">${mr.name}</a></td>
                                <td>${mr.material_request_type}</td>
                                <td>${mr.supplier || '-'}</td>
                                <td>${mr.warehouse || '-'}</td>
                                <td>${mr.items_count}</td>
                                <td>
                                    <button class="btn btn-primary btn-sm" onclick="frappe.set_route('Form', 'Material Request', '${mr.name}')">
                                        Ouvrir
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

// ================== FONCTIONS DE DEBUG ==================

/**
 * Vérifie les BOMs disponibles pour un item
 */
function check_item_boms(item_code) {
    frappe.call({
        method: 'custom_nedlog.production_analysis.get_available_boms_for_item',
        args: {
            item_code: item_code
        },
        
        callback: function(response) {
            console.log('Response for BOM check:', response);
            console.log('BOMs pour item ' + item_code + ':', response.message);
            const data = response.message;
            frappe.msgprint({
                title: 'BOMs pour ' + item_code,
                message: `
                    <div>
                        <p><strong>Total BOMs:</strong> ${data.total_boms}</p>
                        <p><strong>BOMs Actifs:</strong> ${data.active_boms}</p>
                        <p><strong>BOMs Par Défaut:</strong> ${data.default_boms}</p>
                        <p><strong>BOMs Soumis:</strong> ${data.submitted_boms}</p>
                        <p><strong>BOMs Valides:</strong> ${data.valid_boms}</p>
                        <hr>
                        <table class="table table-bordered">
                            <thead>
                                <tr><th>BOM</th><th>Actif</th><th>Défaut</th><th>Statut</th></tr>
                            </thead>
                            <tbody>
                                ${data.boms.map(bom => `
                                    <tr>
                                        <td>${bom.name}</td>
                                        <td>${bom.is_active ? '✓' : '✗'}</td>
                                        <td>${bom.is_default ? '✓' : '✗'}</td>
                                        <td>${bom.docstatus}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `,
                indicator: 'blue'
            });
        },
        error: function(error) {
            console.error('Error checking BOMs:', error);
        }
    });
}

/**
 * Test direct d'un BOM spécifique
 */
function test_bom_analysis(bom_no, qty = 1) {
    frappe.call({
        method: 'custom_nedlog.production_analysis.debug_bom_analysis',
        args: {
            bom_no: bom_no,
            qty: qty
        },
        callback: function(response) {
            console.log('Debug BOM Analysis:', response.message);
            const data = response.message;
            frappe.msgprint({
                title: 'Debug BOM Analysis - ' + bom_no,
                message: `
                    <div>
                        <p><strong>BOM Existe:</strong> ${data.bom_exists ? '✓' : '✗'}</p>
                        <p><strong>BOM Actif:</strong> ${data.bom_active ? '✓' : '✗'}</p>
                        <p><strong>BOM Par Défaut:</strong> ${data.bom_default ? '✓' : '✗'}</p>
                        <p><strong>BOM Statut:</strong> ${data.bom_status}</p>
                        <p><strong>BOM Valide:</strong> ${data.bom_valid ? '✓' : '✗'}</p>
                        <p><strong>Items BOM:</strong> ${data.bom_items_count}</p>
                        <p><strong>Matières Calculées:</strong> ${data.materials_count}</p>
                        <hr>
                        <pre>${JSON.stringify(data.materials, null, 2)}</pre>
                    </div>
                `,
                indicator: data.bom_valid ? 'green' : 'orange'
            });
        },
        error: function(error) {
            console.error('Error in BOM debug:', error);
        }
    });
}

// ================== FONCTIONS UTILITAIRES HTML ==================

function generate_consolidated_items_rows(consolidated_items) {
    if (!consolidated_items || consolidated_items.length === 0) {
        return '<tr><td colspan="5" class="text-center text-muted">Aucun item consolidé</td></tr>';
    }
    
    return consolidated_items.map(item => `
        <tr>
            <td><a href="/app/item/${item.item_code}" target="_blank">${item.item_code}</a></td>
            <td>${item.description || ''}</td>
            <td class="text-right"><strong>${item.total_qty}</strong></td>
            <td>${item.bom_no ? `<a href="/app/bom/${item.bom_no}" target="_blank">${item.bom_no}</a>` : 'Aucun BOM'}</td>
            <td>${item.warehouse || ''}</td>
        </tr>
    `).join('');
}

function generate_raw_materials_rows(raw_materials) {
    if (!raw_materials || raw_materials.length === 0) {
        return '<tr><td colspan="8" class="text-center text-muted">Aucune matière première</td></tr>';
    }
    
    return raw_materials.map(material => {
        const shortage = (material.required_qty || 0) - (material.available_qty || 0);
        const has_shortage = shortage > 0;
        const row_class = has_shortage ? 'shortage-row' : 'available-row';
        const status = has_shortage ? 'MANQUE' : 'DISPONIBLE';
        
        return `
            <tr class="${row_class}">
                <td><a href="/app/item/${material.item_code}" target="_blank">${material.item_code}</a></td>
                <td>${material.item_name || ''}</td>
                <td class="text-right">${material.required_qty || 0}</td>
                <td class="text-right">${material.available_qty || 0}</td>
                <td class="text-right ${has_shortage ? 'text-danger' : 'text-success'}">
                    <strong>${Math.max(0, shortage)}</strong>
                </td>
                <td>${material.supplier_name || material.default_supplier || 'Non défini'}</td>
                <td>${material.customer_po_display || ''}</td>
                <td>
                    <span class="badge ${has_shortage ? 'badge-danger' : 'badge-success'}">${status}</span>
                </td>
            </tr>
        `;
    }).join('');
}