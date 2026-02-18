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
        title: ` Analyse des Besoins de Production - ${sales_order_names.length} commande(s)`,
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
    
    // Rendre les fonctions d'export disponibles globalement
    window.printMaterialRequirementsReport = printMaterialRequirementsReport;
    window.generateMaterialRequirementsPDF = generateMaterialRequirementsPDF;
    window.emailMaterialRequirementsReport = emailMaterialRequirementsReport;
    
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
        title: ` Création Material Requests - ${sales_order_names.length} commande(s)`,
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
                    // Debug: afficher les données reçues
                    console.log('📊 Données de stock reçues:', response.message);
                    
                    // Debug: vérifier les données des entrepôts
                    if (response.message.raw_materials_requirements) {
                        const materialsWithWarehouses = response.message.raw_materials_requirements.filter(
                            m => m.warehouses && m.warehouses.length > 0
                        );
                        console.log(`🏭 ${materialsWithWarehouses.length} matières avec données d'entrepôts`);
                        
                        materialsWithWarehouses.slice(0, 3).forEach(material => {
                            console.log(`   📦 ${material.item_code}: ${material.warehouses.length} entrepôts`, material.warehouses);
                        });
                    }
                    
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
    // Debug automatique des données d'emplacements
    debug_warehouses_data(analysis_data);
    
    const html_content = generate_analysis_html(analysis_data);
    dialog.fields_dict.analysis_content.$wrapper.html(html_content);
    
    // Attacher les événements après que le DOM soit mis à jour
    setTimeout(() => {
        // Attacher l'événement de changement aux checkboxes
        Object.keys(AVAILABLE_COLUMNS).forEach(colKey => {
            const checkbox = document.getElementById(`col-${colKey}`);
            if (checkbox) {
                checkbox.addEventListener('change', refreshTableDisplay);
            }
        });
        
        // Actualiser l'affichage initial
        refreshTableDisplay();
    }, 100);
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
                .preferences-panel {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 15px 0;
                }
                .preferences-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 10px;
                    margin-top: 10px;
                }
                .preference-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .preference-item input[type="checkbox"] {
                    margin: 0;
                }
                .column-hidden { display: none !important; }
                .detail-row { background-color: #fff; }
                .total-row { 
                    background-color: #f8f9fa; 
                    font-weight: bold; 
                    border-top: 2px solid #007bff;
                }
                .separator-row { border: none !important; }
            </style>
            
            <!-- Statistiques -->
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
                    <div class="stat-number">${analysis_data.stats?.total_raw_materials_unique || 0}</div>
                    <div class="stat-label">Matières Uniques</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${analysis_data.stats?.items_with_shortage || 0}</div>
                    <div class="stat-label">Items en Manque</div>
                </div>
            </div>
            
            <!-- Items Finis Consolidés -->
            <h3 class="section-title"> Items Finis Consolidés</h3>
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
            
            <h3 class="section-title"> Besoins en Matières Premières</h3>
            
            <!-- Actions Toolbar -->
            <div style="margin-bottom: 15px; display: flex; gap: 10px; align-items: center;">
                <button class="btn btn-sm btn-primary" onclick="printMaterialRequirementsReport()">
                    <i class="fa fa-print"></i> Imprimer
                </button>
                <button class="btn btn-sm btn-success" onclick="generateMaterialRequirementsPDF()">
                    <i class="fa fa-file-pdf-o"></i> Générer PDF
                </button>
                <button class="btn btn-sm btn-info" onclick="emailMaterialRequirementsReport()">
                    <i class="fa fa-envelope"></i> Envoyer par Email
                </button>
            </div>
            
            <!-- Panel de Préférences -->
            <div class="preferences-panel">
                <h5 style="margin: 0 0 10px 0; color: #495057;">
                    <i class="fa fa-cog"></i> Préférences d'Affichage
                </h5>
                <div class="preferences-grid">
                    <div class="preference-item">
                        <input type="checkbox" id="col-item-code" checked>
                        <label for="col-item-code">Item Code</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-description" checked>
                        <label for="col-description">Description</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-qty-required" checked>
                        <label for="col-qty-required">Qty Requise</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-stock-available" checked>
                        <label for="col-stock-available">Stock Disponible</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-shortage" checked>
                        <label for="col-shortage">Manque</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-warehouses-list" checked>
                        <label for="col-warehouses-list">Emplacements</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-warehouses-qty" checked>
                        <label for="col-warehouses-qty">Qtés par Emplacement</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-supplier" checked>
                        <label for="col-supplier">Fournisseur</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-order-number" checked>
                        <label for="col-order-number">Order Number</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-status" checked>
                        <label for="col-status">Statut</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-item-group">
                        <label for="col-item-group">Item Group</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-brand">
                        <label for="col-brand">Brand</label>
                    </div>
                    <div class="preference-item">
                        <input type="checkbox" id="col-weight">
                        <label for="col-weight">Weight</label>
                    </div>
                </div>
                <button class="btn btn-sm btn-primary" style="margin-top: 10px;" onclick="refreshTableDisplay()">
                    <i class="fa fa-refresh"></i> Actualiser Affichage
                </button>
            </div>
            
            <div class="analysis-section">
                <table class="data-table" id="raw-materials-table">
                    ${generate_dynamic_table_header()}
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
 * Debug: Vérifier les données d'emplacements
 */
function debug_warehouses_data(analysis_data) {
    console.log('🔍 DEBUG EMPLACEMENTS - Analyse des données reçues');
    
    if (!analysis_data || !analysis_data.raw_materials_requirements) {
        console.log('❌ Aucune données de matières premières trouvées');
        return;
    }
    
    const materials = analysis_data.raw_materials_requirements;
    console.log(`📋 Total matières: ${materials.length}`);
    
    // Compter les types
    const detailRows = materials.filter(m => m.type === 'detail');
    const totalRows = materials.filter(m => m.type === 'total');
    
    console.log(`   📄 Détails: ${detailRows.length}`);
    console.log(`   📊 Totaux: ${totalRows.length}`);
    
    // Vérifier les warehouses dans les totaux
    const totalRowsWithWarehouses = totalRows.filter(m => m.warehouses && m.warehouses.length > 0);
    console.log(`   🏭 Totaux avec entrepôts: ${totalRowsWithWarehouses.length}`);
    
    if (totalRowsWithWarehouses.length > 0) {
        console.log('🏭 Exemples d\'entrepôts:');
        totalRowsWithWarehouses.slice(0, 5).forEach((material, index) => {
            console.log(`   ${index + 1}. ${material.item_code}:`);
            material.warehouses.forEach(w => {
                console.log(`      📦 ${w.warehouse}: ${w.actual_qty} (disponible)`);
            });
        });
    } else {
        console.log('⚠️ Aucun total avec données d\'entrepôts trouvé');
        
        // Debug plus poussé
        if (totalRows.length > 0) {
            console.log('🔍 Structure du premier total:', totalRows[0]);
        }
    }
    
    return {
        total_materials: materials.length,
        detail_rows: detailRows.length,
        total_rows: totalRows.length,
        totals_with_warehouses: totalRowsWithWarehouses.length
    };
}

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

// Configuration des colonnes disponibles
const AVAILABLE_COLUMNS = {
    'item-code': { label: 'Item Code', field: 'item_code', always_visible: false },
    'description': { label: 'Description', field: 'item_name', always_visible: false },
    'qty-required': { label: 'Qty Requise', field: 'required_qty', always_visible: false },
    'stock-available': { label: 'Stock Disponible', field: 'available_qty', always_visible: false },
    'shortage': { label: 'Manque', field: 'shortage_qty', always_visible: false },
    'warehouses-list': { label: 'Emplacements', field: 'warehouses_list', always_visible: false },
    'warehouses-qty': { label: 'Qtés par Emplacement', field: 'warehouses_qty', always_visible: false },
    'supplier': { label: 'Fournisseur', field: 'supplier_name', always_visible: false },
    'order-number': { label: 'Order Number', field: 'customer_po_no', always_visible: false },
    'status': { label: 'Statut', field: 'status', always_visible: false },
    'item-group': { label: 'Item Group', field: 'item_group', always_visible: false },
    'brand': { label: 'Brand', field: 'brand', always_visible: false },
    'weight': { label: 'Weight', field: 'weight_per_unit', always_visible: false }
};

function generate_dynamic_table_header() {
    let header = '<thead><tr>';
    
    Object.keys(AVAILABLE_COLUMNS).forEach(colKey => {
        const col = AVAILABLE_COLUMNS[colKey];
        header += `<th class="col-${colKey}">${col.label}</th>`;
    });
    
    header += '</tr></thead>';
    return header;
}

function getVisibleColumns() {
    const visible = [];
    Object.keys(AVAILABLE_COLUMNS).forEach(colKey => {
        const checkbox = document.getElementById(`col-${colKey}`);
        if (checkbox && checkbox.checked) {
            visible.push(colKey);
        }
    });
    return visible;
}

function refreshTableDisplay() {
    const visibleColumns = getVisibleColumns();
    
    // Masquer/Afficher les colonnes d'en-tête
    Object.keys(AVAILABLE_COLUMNS).forEach(colKey => {
        const isVisible = visibleColumns.includes(colKey);
        const headerCells = document.querySelectorAll(`th.col-${colKey}`);
        const dataCells = document.querySelectorAll(`td.col-${colKey}`);
        
        headerCells.forEach(cell => {
            if (isVisible) {
                cell.classList.remove('column-hidden');
            } else {
                cell.classList.add('column-hidden');
            }
        });
        
        dataCells.forEach(cell => {
            if (isVisible) {
                cell.classList.remove('column-hidden');
            } else {
                cell.classList.add('column-hidden');
            }
        });
    });
}

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
        const colCount = Object.keys(AVAILABLE_COLUMNS).length;
        return `<tr><td colspan="${colCount}" class="text-center text-muted">Aucune matière première</td></tr>`;
    }
    
    // Séparer les détails des totaux
    const details = raw_materials.filter(m => m.type === 'detail');
    const totals = raw_materials.filter(m => m.type === 'total');
    
    let html = '';
    
    // Grouper les détails par item_code
    const groupedDetails = {};
    details.forEach(material => {
        if (!groupedDetails[material.item_code]) {
            groupedDetails[material.item_code] = [];
        }
        groupedDetails[material.item_code].push(material);
    });
    
    // Afficher chaque groupe (item + ses orders + total)
    Object.keys(groupedDetails).forEach(item_code => {
        const itemDetails = groupedDetails[item_code];
        const itemTotal = totals.find(t => t.item_code === item_code);
        
        // Afficher les lignes de détail
        itemDetails.forEach((material, index) => {
            html += generate_material_row(material, 'detail');
        });
        
        // Afficher la ligne de total pour cet item
        if (itemTotal) {
            html += generate_material_row(itemTotal, 'total');
            
            // Ajouter une ligne de séparation
            const colCount = Object.keys(AVAILABLE_COLUMNS).length;
            html += `<tr class="separator-row"><td colspan="${colCount}" style="height: 10px; border: none;"></td></tr>`;
        }
    });
    
    return html;
}

function generate_material_row(material, rowType) {
    let html = `<tr class="${rowType}-row">`;
    
    // Générer chaque cellule selon la configuration des colonnes
    Object.keys(AVAILABLE_COLUMNS).forEach(colKey => {
        const col = AVAILABLE_COLUMNS[colKey];
        let cellContent = '';
        
        switch(colKey) {
            case 'item-code':
                cellContent = `<a href="/app/item/${material.item_code}" target="_blank">${material.item_code}</a>`;
                break;
            case 'description':
                cellContent = material.item_name || '';
                break;
            case 'qty-required':
                if (rowType === 'detail') {
                    cellContent = `<span class="text-right">${material.required_qty || 0}</span>`;
                } else {
                    cellContent = `<span class="text-right"><strong>${material.total_required_qty || 0}</strong></span>`;
                }
                break;
            case 'stock-available':
                if (rowType === 'total') {
                    cellContent = `<span class="text-right"><strong>${material.available_qty || 0}</strong></span>`;
                } else {
                    cellContent = '<span class="text-center">-</span>';
                }
                break;
            case 'shortage':
                if (rowType === 'total') {
                    const shortage = Math.max(0, (material.total_required_qty || 0) - (material.available_qty || 0));
                    const has_shortage = shortage > 0;
                    cellContent = `<span class="text-right ${has_shortage ? 'text-danger' : 'text-success'}"><strong>${shortage}</strong></span>`;
                } else {
                    cellContent = '<span class="text-center">-</span>';
                }
                break;
            case 'warehouses-list':
                if (rowType === 'total' && material.warehouses && material.warehouses.length > 0) {
                    const warehouseNames = material.warehouses.map(w => w.warehouse).join(', ');
                    cellContent = `<div style="font-size: 11px;">${warehouseNames}</div>`;
                } else {
                    cellContent = '<span class="text-center">-</span>';
                }
                break;
            case 'warehouses-qty':
                if (rowType === 'total' && material.warehouses && material.warehouses.length > 0) {
                    const warehouseDetails = material.warehouses.map(w => 
                        `<div style="margin: 2px 0; padding: 2px 5px; background: #f8f9fa; border-radius: 3px;">
                            <strong>${w.warehouse}:</strong> <span style="color: ${w.actual_qty > 0 ? '#28a745' : '#dc3545'};">${w.actual_qty || 0}</span>
                        </div>`
                    ).join('');
                    cellContent = `<div style="font-size: 11px;">${warehouseDetails}</div>`;
                } else {
                    cellContent = '<span class="text-center">-</span>';
                }
                break;
            case 'supplier':
                cellContent = material.supplier_name || material.default_supplier || 'Non défini';
                break;
            case 'order-number':
                if (rowType === 'detail') {
                    cellContent = `<strong>${material.customer_po_no || ''}</strong>`;
                } else {
                    cellContent = `<em>TOTAL (${material.orders_count || 0} orders)</em>`;
                }
                break;
            case 'status':
                if (rowType === 'detail') {
                    cellContent = '<span class="badge badge-info">DÉTAIL</span>';
                } else {
                    const shortage = Math.max(0, (material.total_required_qty || 0) - (material.available_qty || 0));
                    const has_shortage = shortage > 0;
                    const status = has_shortage ? 'MANQUE' : 'DISPONIBLE';
                    cellContent = `<span class="badge ${has_shortage ? 'badge-danger' : 'badge-success'}">${status}</span>`;
                }
                break;
            case 'item-group':
                cellContent = material.item_group || '-';
                break;
            case 'brand':
                cellContent = material.brand || '-';
                break;
            case 'weight':
                cellContent = material.weight_per_unit || '-';
                break;
            default:
                cellContent = '-';
        }
        
        html += `<td class="col-${colKey}">${cellContent}</td>`;
    });
    
    html += '</tr>';
    return html;
}

// ================== FONCTIONS D'IMPRESSION ET EXPORT ==================

/**
 * Extraire le contenu visible du tableau pour l'impression
 */
function extractVisibleTableContent(tableElement) {
    if (!tableElement) {
        return '<p>Aucun tableau trouvé</p>';
    }
    
    const visibleColumns = [];
    const headers = tableElement.querySelectorAll('thead th');
    
    // Déterminer quelles colonnes sont visibles
    headers.forEach((header, index) => {
        if (!header.classList.contains('column-hidden') && !header.style.display === 'none') {
            visibleColumns.push(index);
        }
    });
    
    let tableHtml = '<table>';
    
    // En-tête du tableau
    tableHtml += '<thead><tr>';
    headers.forEach((header, index) => {
        if (visibleColumns.includes(index)) {
            tableHtml += `<th>${header.textContent.trim()}</th>`;
        }
    });
    tableHtml += '</tr></thead>';
    
    // Corps du tableau - inclure TOUTES les lignes visibles
    tableHtml += '<tbody>';
    const rows = tableElement.querySelectorAll('tbody tr');
    
    let visibleRowCount = 0;
    rows.forEach((row, rowIndex) => {
        // Vérifier si la ligne est visible (pas cachée par CSS ou style)
        const isVisible = !row.classList.contains('separator-row') && 
                         !row.classList.contains('hidden') && 
                         row.style.display !== 'none' &&
                         !row.hidden;
        
        if (isVisible) {
            visibleRowCount++;
            const rowClass = row.className || '';
            tableHtml += `<tr class="${rowClass}">`;
            
            const cells = row.querySelectorAll('td');
            cells.forEach((cell, cellIndex) => {
                if (visibleColumns.includes(cellIndex)) {
                    // Préserver le contenu exact de la cellule
                    let cellContent = cell.textContent.trim();
                    if (!cellContent || cellContent === '') {
                        cellContent = '-';
                    }
                    tableHtml += `<td>${cellContent}</td>`;
                }
            });
            
            tableHtml += '</tr>';
        }
    });
    
    tableHtml += '</tbody></table>';
    
    // Ajouter un résumé en bas si plusieurs commandes
    if (visibleRowCount > 1) {
        tableHtml += `<div class="print-summary" style="margin-top: 20px; font-style: italic; color: #666;">
            Total: ${visibleRowCount} lignes extraites du tableau d'analyse
        </div>`;
    }
    
    return tableHtml;
}

/**
 * Imprimer le rapport des besoins en matières premières
 */
function printMaterialRequirementsReport() {
    const tableElement = document.getElementById('raw-materials-table');
    if (!tableElement) {
        frappe.msgprint('Aucune donnée à imprimer - tableau non trouvé');
        return;
    }
    
    const totalRows = tableElement.querySelectorAll('tbody tr').length;
    if (totalRows === 0) {
        frappe.msgprint('Le tableau ne contient aucune donnée');
        return;
    }
    
    // Créer une fenêtre d'impression avec le contenu du tableau
    const printWindow = window.open('', '_blank', 'width=800,height=600');
    
    const printContent = `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Besoins en Matières Premières</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    margin: 20px;
                    background: white;
                    color: black;
                }
                h1 { 
                    color: #2c3e50; 
                    text-align: center; 
                    margin-bottom: 30px;
                    font-size: 24px;
                }
                .meta-info { 
                    margin-bottom: 20px; 
                    padding: 15px; 
                    background: #f8f9fa; 
                    border-radius: 5px;
                    border: 1px solid #dee2e6;
                }
                table { 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin-top: 20px;
                    background: white;
                }
                th, td { 
                    border: 1px solid #333; 
                    padding: 8px; 
                    text-align: left; 
                    font-size: 11px; 
                }
                th { 
                    background-color: #4a90e2 !important; 
                    color: white !important; 
                    font-weight: bold; 
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }
                .detail-row td { 
                    background-color: #fff !important;
                }
                .total-row td { 
                    background-color: #f8f9fa !important; 
                    font-weight: bold;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }
                .separator-row { 
                    display: none !important; 
                }
                .column-hidden { 
                    display: none !important; 
                }
                @media print {
                    body { margin: 10px; }
                    .no-print { display: none !important; }
                    table { page-break-inside: auto; }
                    tr { page-break-inside: avoid; page-break-after: auto; }
                }
            </style>
        </head>
        <body>
            <h1> Rapport des Besoins en Matières Premières</h1>
            <div class="meta-info">
                <strong>Date de génération:</strong> ${new Date().toLocaleDateString('fr-FR')}<br>
                <strong>Heure:</strong> ${new Date().toLocaleTimeString('fr-FR')}<br>
                <strong>Généré par:</strong> ${frappe.session.user}
            </div>
            ${tableElement.outerHTML}
        </body>
        </html>
    `;
    
    console.log(' IMPRESSION - Contenu HTML final:', printContent.substring(0, 800) + '...');
    
    printWindow.document.write(printContent);
    printWindow.document.close();
    
    // Attendre que le contenu soit chargé avant d'imprimer
    printWindow.onload = function() {
        printWindow.focus();
        printWindow.print();
        
        // Fermer la fenêtre après l'impression ou si l'utilisateur annule
        // Mais seulement après un délai pour permettre l'impression
        setTimeout(function() {
            printWindow.close();
        }, 1000);
    };
    
    // Si onload ne se déclenche pas, fallback après délai
    setTimeout(function() {
        if (printWindow && !printWindow.closed) {
            printWindow.focus();
            printWindow.print();
        }
    }, 500);
}

/**
 * Générer un PDF du rapport
 */
function generateMaterialRequirementsPDF() {
    const tableElement = document.getElementById('raw-materials-table');
    if (!tableElement) {
        frappe.msgprint('Aucune donnée à exporter en PDF');
        return;
    }
    
    // Préparer les données pour l'export PDF
    const visibleColumns = getVisibleColumns();
    const tableData = extractTableDataForPDF(tableElement, visibleColumns);
    
    frappe.call({
        method: 'custom_nedlog.production_analysis.generate_material_requirements_pdf',
        args: {
            table_data: tableData,
            visible_columns: visibleColumns,
            meta_info: {
                generated_date: new Date().toLocaleDateString('fr-FR'),
                generated_time: new Date().toLocaleTimeString('fr-FR'),
                generated_by: frappe.session.user
            }
        },
        callback: function(response) {
            if (response.message && response.message.file_url) {
                // Télécharger le PDF généré
                window.open(response.message.file_url, '_blank');
                frappe.msgprint({
                    message: 'PDF généré avec succès!',
                    indicator: 'green'
                });
            } else {
                frappe.msgprint({
                    message: 'Erreur lors de la génération du PDF',
                    indicator: 'red'
                });
            }
        },
        error: function(error) {
            frappe.msgprint({
                message: 'Erreur lors de la génération du PDF: ' + error.message,
                indicator: 'red'
            });
        }
    });
}

/**
 * Envoyer le rapport par email
 */
function emailMaterialRequirementsReport() {
    const tableElement = document.getElementById('raw-materials-table');
    if (!tableElement) {
        frappe.msgprint('Aucune donnée à envoyer');
        return;
    }
    
    // Dialog pour saisir les détails de l'email
    const emailDialog = new frappe.ui.Dialog({
        title: '📧 Envoyer le Rapport par Email',
        fields: [
            {
                fieldtype: 'Data',
                fieldname: 'recipients',
                label: 'Destinataires (séparés par des virgules)',
                reqd: 1,
                description: 'exemple: user1@company.com, user2@company.com'
            },
            {
                fieldtype: 'Data',
                fieldname: 'subject',
                label: 'Sujet',
                default: `Rapport Besoins Matières Premières - ${new Date().toLocaleDateString('fr-FR')}`,
                reqd: 1
            },
            {
                fieldtype: 'Text Editor',
                fieldname: 'message',
                label: 'Message',
                default: `Bonjour,\n\nVeuillez trouver ci-joint le rapport des besoins en matières premières.\n\nCordialement,\n${frappe.session.user}`
            },
            {
                fieldtype: 'Check',
                fieldname: 'attach_pdf',
                label: 'Joindre le rapport en PDF',
                default: 1
            }
        ],
        primary_action_label: 'Envoyer',
        primary_action: function(values) {
            sendMaterialRequirementsEmail(values, tableElement);
            emailDialog.hide();
        }
    });
    
    emailDialog.show();
}

/**
 * Fonction pour envoyer effectivement l'email
 */
function sendMaterialRequirementsEmail(emailData, tableElement) {
    const visibleColumns = getVisibleColumns();
    const tableData = extractTableDataForPDF(tableElement, visibleColumns);
    
    frappe.call({
        method: 'custom_nedlog.production_analysis.send_material_requirements_email',
        args: {
            recipients: emailData.recipients,
            subject: emailData.subject,
            message: emailData.message,
            attach_pdf: emailData.attach_pdf,
            table_data: tableData,
            visible_columns: visibleColumns,
            meta_info: {
                generated_date: new Date().toLocaleDateString('fr-FR'),
                generated_time: new Date().toLocaleTimeString('fr-FR'),
                generated_by: frappe.session.user
            }
        },
        callback: function(response) {
            if (response.message && response.message.success) {
                frappe.msgprint({
                    message: 'Email envoyé avec succès!',
                    indicator: 'green'
                });
            } else {
                frappe.msgprint({
                    message: 'Erreur lors de l\'envoi de l\'email',
                    indicator: 'red'
                });
            }
        },
        error: function(error) {
            frappe.msgprint({
                message: 'Erreur lors de l\'envoi: ' + error.message,
                indicator: 'red'
            });
        }
    });
}

/**
 * Extraire les données du tableau pour l'export
 */
function extractTableDataForPDF(tableElement, visibleColumns) {
    const rows = tableElement.querySelectorAll('tbody tr');
    const data = [];
    
    rows.forEach(row => {
        const rowData = {};
        const cells = row.querySelectorAll('td');
        
        if (cells.length > 0 && !row.classList.contains('separator-row')) {
            visibleColumns.forEach((colKey, index) => {
                if (cells[index] && !cells[index].classList.contains('column-hidden')) {
                    const colConfig = AVAILABLE_COLUMNS[colKey];
                    rowData[colConfig.label] = cells[index].textContent.trim();
                }
            });
            
            // Identifier le type de ligne
            if (row.classList.contains('detail-row')) {
                rowData['_type'] = 'detail';
            } else if (row.classList.contains('total-row')) {
                rowData['_type'] = 'total';
            }
            
            data.push(rowData);
        }
    });
    
    return data;
}