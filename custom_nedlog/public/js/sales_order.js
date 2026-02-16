// Customisation pour Sales Order - Bouton BOM Info
frappe.ui.form.on('Sales Order', {
    refresh: function(frm) {
        // Ajouter le bouton BOM Info si le document est sauvegardé
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('BOM Info'), function() {
                show_bom_info_dialog([frm.doc.name]);
            }, __('Manufacturing'));
            
            // Ajouter bouton pour sélection multiple
            frm.add_custom_button(__('Multi BOM Analysis'), function() {
                show_multiple_sales_order_selector();
            }, __('Manufacturing'));
        }
    }
});



// Fonction pour sélecteur de Sales Orders multiples avec interface ERPNext native
function show_multiple_sales_order_selector() {
    // Utiliser le dialogue natif ERPNext
    let d = new frappe.ui.Dialog({
        title: __('📊 Sélectionner Sales Orders pour analyse BOM'),
        fields: [
            {
                fieldtype: 'Section Break',
                fieldname: 'selection_section'
            },
            {
                fieldtype: 'MultiSelectPills',
                fieldname: 'sales_orders',
                label: __('Sales Orders'),
                reqd: 1,
                get_data: function(txt) {
                    return frappe.db.get_link_options('Sales Order', txt, {
                        'docstatus': 1,
                        'status': ['not in', ['Cancelled', 'Closed']]
                    });
                }
            },
            {
                fieldtype: 'Column Break',
                fieldname: 'col_break'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'help_html',
                options: `
                    <div class="alert alert-info">
                        <h6><i class="fa fa-info-circle"></i> Instructions:</h6>
                        <ul style="margin-bottom: 0;">
                            <li>Sélectionnez une ou plusieurs commandes clients</li>
                            <li>L'analyse consolidera automatiquement tous les BOMs</li>
                            <li>Vous obtiendrez un rapport détaillé des matières premières</li>
                        </ul>
                    </div>
                `
            }
        ],
        size: 'large',
        primary_action_label: __('🔍 Analyser BOMs'),
        primary_action: function(values) {
            if (!values.sales_orders || values.sales_orders.length === 0) {
                frappe.msgprint({
                    title: __('Erreur de sélection'),
                    message: __('Veuillez sélectionner au moins une Sales Order'),
                    indicator: 'red'
                });
                return;
            }
            d.hide();
            show_bom_analysis_dialog(values.sales_orders);
        },
        secondary_action_label: __('Annuler')
    });
    
    d.show();
    d.get_close_btn().on('click', () => d.hide());
}

// Fonction principale pour afficher le dialogue BOM Info avec interface native ERPNext
function show_bom_info_dialog(sales_orders) {
    show_bom_analysis_dialog(sales_orders);
}

// Fonction principale avec interface native ERPNext ressemblant à la photo
function show_bom_analysis_dialog(sales_orders) {
    // Créer le dialogue ERPNext natif avec loading
    let analysis_dialog = new frappe.ui.Dialog({
        title: `📊 ${sales_orders.length > 1 ? 'Analyse BOM Consolidée' : 'Analyse BOM'} - ${sales_orders.length} commande(s)`,
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'loading_area',
                options: `
                    <div class="text-center" style="padding: 40px;">
                        <div class="spinner-border text-primary" role="status">
                            <span class="sr-only">Chargement...</span>
                        </div>
                        <p class="mt-3">Analyse des BOMs en cours...</p>
                        <small class="text-muted">Extraction des matières premières et vérification des stocks</small>
                    </div>
                `
            }
        ],
        size: 'extra-large'
    });
    
    analysis_dialog.show();
    
    // Appeler l'API selon le nombre de commandes
    let method = sales_orders.length === 1 ? 
        'custom_nedlog.api.get_sales_order_bom_info' : 
        'custom_nedlog.api.get_multiple_sales_orders_bom_info';
    
    let args = sales_orders.length === 1 ? 
        { sales_order: sales_orders[0] } : 
        { sales_orders: JSON.stringify(sales_orders) };
    
    frappe.call({
        method: method,
        args: args,
        callback: function(response) {
            analysis_dialog.fields_dict.loading_area.$wrapper.empty();
            
            if (response.message && response.message.success) {
                // Créer l'interface native avec les données
                create_native_bom_interface(analysis_dialog, response.message, sales_orders);
            } else {
                analysis_dialog.fields_dict.loading_area.$wrapper.html(`
                    <div class="alert alert-danger">
                        <h6><i class="fa fa-exclamation-triangle"></i> Erreur lors du chargement</h6>
                        <p>${response.message ? response.message.error : 'Erreur inconnue lors de la récupération des données BOM'}</p>
                    </div>
                `);
            }
        },
        freeze: true,
        freeze_message: __("Analyse des BOMs en cours...")
    });
}

// Fonction pour créer l'interface native ERPNext ressemblant à la photo
function create_native_bom_interface(dialog, data, sales_orders) {
    // Préparer les données pour l'affichage en tableau natif
    let consolidated_materials = {};
    let all_orders_data = [];
    
    if (sales_orders.length === 1) {
        // Une seule commande
        all_orders_data.push(data);
        if (data.bom_info && data.bom_info.length > 0) {
            data.bom_info.forEach(item => {
                if (item.has_bom && item.raw_materials) {
                    item.raw_materials.forEach(material => {
                        consolidate_material(consolidated_materials, material, data.sales_order);
                    });
                }
            });
        }
    } else {
        // Multiples commandes
        all_orders_data = data.all_bom_info || [];
        if (data.total_raw_materials) {
            Object.keys(data.total_raw_materials).forEach(item_code => {
                let material = data.total_raw_materials[item_code];
                consolidated_materials[item_code] = {
                    item_code: item_code,
                    item_name: material.item_name,
                    total_needed: material.total_needed,
                    total_available: material.total_available,
                    uom: material.uom,
                    difference: material.total_available - material.total_needed,
                    orders: sales_orders
                };
            });
        }
    }
    
    // Remplacer le contenu du dialogue avec l'interface native
    dialog.$wrapper.find('.modal-body').html(`
        <div class="bom-analysis-container">
            ${get_bom_css()}
            <!-- Header avec résumé -->
            <div class="row mb-4">
                <div class="col-md-12">
                    <div class="card border-primary">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">
                                <i class="fa fa-chart-line"></i> 
                                ${sales_orders.length > 1 ? 'Analyse Consolidée' : 'Analyse BOM'} - 
                                ${sales_orders.join(', ')}
                            </h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-3">
                                    <div class="stat-card bg-light">
                                        <h4 class="text-primary">${sales_orders.length}</h4>
                                        <span>Commande(s)</span>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="stat-card bg-light">
                                        <h4 class="text-info">${Object.keys(consolidated_materials).length}</h4>
                                        <span>Articles nécessaires</span>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="stat-card bg-light">
                                        <h4 class="text-success">${calculate_sufficient_items(consolidated_materials)}</h4>
                                        <span>En stock suffisant</span>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="stat-card bg-light">
                                        <h4 class="text-warning">${Object.keys(consolidated_materials).length - calculate_sufficient_items(consolidated_materials)}</h4>
                                        <span>À commander</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Tableau de données ressemblant à la photo -->
            <div class="row">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header bg-light">
                            <h6 class="mb-0">
                                <i class="fa fa-table"></i> 
                                Détail des Matières Premières Nécessaires
                            </h6>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-striped table-hover mb-0" id="materials-table">
                                    <thead class="bg-primary text-white">
                                        <tr>
                                            <th style="width: 15%;">Code Article</th>
                                            <th style="width: 25%;">Description</th>
                                            <th style="width: 12%;">Qté Nécessaire</th>
                                            <th style="width: 12%;">Stock Dispo.</th>
                                            <th style="width: 8%;">Unité</th>
                                            <th style="width: 12%;">Différence</th>
                                            <th style="width: 10%;">Statut</th>
                                            <th style="width: 6%;">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${generate_materials_table_rows(consolidated_materials)}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Actions de masse -->
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card border-warning">
                        <div class="card-body text-center">
                            <button class="btn btn-warning btn-lg mr-2" onclick="generate_material_requests()">
                                <i class="fa fa-shopping-cart"></i> 
                                Créer Demandes d'Achat pour Articles Manquants
                            </button>
                            <button class="btn btn-info btn-lg ml-2" onclick="export_analysis_to_excel()">
                                <i class="fa fa-file-excel-o"></i> 
                                Exporter vers Excel
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `);
}

// Fonction pour consolider les matériaux
function consolidate_material(consolidated, material, order_name) {
    if (!consolidated[material.item_code]) {
        consolidated[material.item_code] = {
            item_code: material.item_code,
            item_name: material.item_name,
            total_needed: 0,
            total_available: material.total_available,
            uom: material.uom,
            difference: 0,
            orders: []
        };
    }
    consolidated[material.item_code].total_needed += material.total_qty;
    consolidated[material.item_code].difference = 
        consolidated[material.item_code].total_available - 
        consolidated[material.item_code].total_needed;
    
    if (!consolidated[material.item_code].orders.includes(order_name)) {
        consolidated[material.item_code].orders.push(order_name);
    }
}

// Fonction pour calculer le nombre d'articles suffisants
function calculate_sufficient_items(materials) {
    return Object.values(materials).filter(m => m.difference >= 0).length;
}

// Fonction pour générer les lignes du tableau des matériaux
function generate_materials_table_rows(materials_data) {
    if (Object.keys(materials_data).length === 0) {
        return `
            <tr>
                <td colspan="8" class="text-center text-muted py-4">
                    <i class="fa fa-info-circle"></i> 
                    Aucune matière première trouvée dans les BOMs
                </td>
            </tr>
        `;
    }
    
    let rows = '';
    Object.values(materials_data).forEach(material => {
        const sufficient = material.difference >= 0;
        const rowClass = sufficient ? '' : 'table-warning';
        const statusBadge = sufficient ? 
            '<span class="badge badge-success"><i class="fa fa-check"></i> Suffisant</span>' :
            '<span class="badge badge-danger"><i class="fa fa-exclamation-triangle"></i> Insuffisant</span>';
        
        const differenceDisplay = material.difference >= 0 ? 
            `<span class="text-success font-weight-bold">+${material.difference.toFixed(2)}</span>` :
            `<span class="text-danger font-weight-bold">${material.difference.toFixed(2)}</span>`;
        
        const actionButton = sufficient ? 
            '<span class="text-muted">-</span>' :
            `<button class="btn btn-sm btn-outline-primary" onclick="create_material_request('${material.item_code}', ${Math.abs(material.difference)}, '${material.uom}')" title="Créer demande d'achat">
                <i class="fa fa-plus"></i>
            </button>`;
        
        rows += `
            <tr class="${rowClass}">
                <td>
                    <a href="/app/item/${material.item_code}" target="_blank" class="font-weight-bold text-primary">
                        ${material.item_code}
                    </a>
                </td>
                <td>${material.item_name || ''}</td>
                <td class="text-right font-weight-bold">${material.total_needed.toFixed(2)}</td>
                <td class="text-right">${material.total_available.toFixed(2)}</td>
                <td class="text-center">${material.uom || ''}</td>
                <td class="text-right">${differenceDisplay}</td>
                <td class="text-center">${statusBadge}</td>
                <td class="text-center">${actionButton}</td>
            </tr>
        `;
    });
    
    return rows;
}

// Fonction pour créer une demande de matériel optimisée
function create_material_request(item_code, qty_needed, uom) {
    frappe.new_doc('Material Request', {
        material_request_type: 'Purchase',
        items: [{
            item_code: item_code,
            qty: qty_needed,
            uom: uom || 'Nos'
        }]
    });
    
    frappe.show_alert({
        message: `Demande d'achat créée pour ${item_code}`,
        indicator: 'green'
    }, 3);
}

// Fonction pour générer des demandes d'achat pour tous les articles manquants
function generate_material_requests() {
    // Cette fonction sera appelée globalement, on récupère les données depuis le tableau
    const table = document.getElementById('materials-table');
    if (!table) return;
    
    const insufficientItems = [];
    const rows = table.querySelectorAll('tbody tr.table-warning');
    
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 6) {
            const itemCode = cells[0].querySelector('a').textContent.trim();
            const qtyText = cells[5].querySelector('span').textContent;
            const qty = Math.abs(parseFloat(qtyText));
            const uom = cells[4].textContent.trim();
            
            if (qty > 0) {
                insufficientItems.push({
                    item_code: itemCode,
                    qty: qty,
                    uom: uom
                });
            }
        }
    });
    
    if (insufficientItems.length === 0) {
        frappe.msgprint({
            title: __('Aucun article manquant'),
            message: __('Tous les articles sont disponibles en stock suffisant.'),
            indicator: 'green'
        });
        return;
    }
    
    // Créer une Material Request avec tous les articles manquants
    frappe.new_doc('Material Request', {
        material_request_type: 'Purchase',
        items: insufficientItems
    });
    
    frappe.show_alert({
        message: `Material Request créée avec ${insufficientItems.length} article(s)`,
        indicator: 'green'
    }, 5);
}

// Fonction pour exporter vers Excel
function export_analysis_to_excel() {
    const table = document.getElementById('materials-table');
    if (!table) return;
    
    // Préparer les données pour l'export
    const data = [];
    const headers = ['Code Article', 'Description', 'Qté Nécessaire', 'Stock Disponible', 'Unité', 'Différence', 'Statut'];
    data.push(headers);
    
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 7) {
            const rowData = [
                cells[0].querySelector('a') ? cells[0].querySelector('a').textContent.trim() : cells[0].textContent.trim(),
                cells[1].textContent.trim(),
                cells[2].textContent.trim(),
                cells[3].textContent.trim(),
                cells[4].textContent.trim(),
                cells[5].textContent.trim(),
                cells[6].textContent.trim()
            ];
            data.push(rowData);
        }
    });
    
    // Appeler l'API d'export
    frappe.call({
        method: 'custom_nedlog.api.export_bom_analysis',
        args: {
            data: JSON.stringify(data),
            filename: `BOM_Analysis_${frappe.datetime.now_date()}.xlsx`
        },
        callback: function(response) {
            if (response.message) {
                window.open(response.message.file_url);
            }
        }
    });
}


// Fonction pour obtenir le CSS amélioré ressemblant à la photo
function get_bom_css() {
    return `
        <style>
            .bom-analysis-container {
                padding: 20px;
                font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
                background-color: #fafbfc;
                min-height: 600px;
            }
            
            .stat-card {
                text-align: center;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #e1e5e9;
                transition: transform 0.2s;
            }
            
            .stat-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            
            .stat-card h4 {
                margin: 0 0 5px 0;
                font-size: 28px;
                font-weight: 700;
            }
            
            .stat-card span {
                color: #6c757d;
                font-size: 13px;
                font-weight: 500;
            }
            
            .frappe-datatable-container {
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                overflow: hidden;
                border: 1px solid #e1e5e9;
            }
            
            /* Styles personnalisés pour ressembler à la photo */
            .dt-scrollable {
                border-radius: 6px !important;
            }
            
            .dt-row {
                border-bottom: 1px solid #f0f0f0 !important;
                transition: background-color 0.2s;
            }
            
            .dt-row:hover {
                background-color: #f8f9fa !important;
            }
            
            .dt-cell {
                padding: 12px 8px !important;
                font-size: 13px !important;
                border-right: 1px solid #f0f0f0;
            }
            
            .dt-cell--header {
                background: linear-gradient(135deg, #4a90e2 0%, #357abd 100%) !important;
                color: white !important;
                font-weight: 600 !important;
                font-size: 13px !important;
                text-align: center !important;
                border-bottom: 2px solid #2c5282 !important;
                padding: 15px 8px !important;
            }
            
            .dt-cell--header:last-child {
                border-right: none;
            }
            
            .dt-cell:last-child {
                border-right: none;
            }
            
            /* Style pour les badges de statut */
            .badge {
                font-size: 11px;
                padding: 6px 10px;
                border-radius: 4px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .badge-success {
                background-color: #28a745 !important;
                color: white;
            }
            
            .badge-danger {
                background-color: #dc3545 !important;
                color: white;
            }
            
            /* Animation de chargement */
            .spinner-border {
                width: 3rem;
                height: 3rem;
            }
            
            /* Responsive design */
            @media (max-width: 768px) {
                .bom-analysis-container {
                    padding: 10px;
                }
                
                .stat-card h4 {
                    font-size: 20px;
                }
                
                .dt-cell {
                    font-size: 11px !important;
                    padding: 8px 4px !important;
                }
            }
            
            /* Style pour les alertes */
            .alert {
                border: none;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .alert-info {
                background-color: #e3f2fd;
                color: #1565c0;
                border-left: 4px solid #2196f3;
            }
            
            .alert-danger {
                background-color: #ffebee;
                color: #c62828;
                border-left: 4px solid #f44336;
            }
        </style>
    `;
}

