{
    "name": "Line Balancing Connector",
    "summary": "Two-way sync between Odoo MRP and the Apparel Line Balancing service",
    "description": """
Pulls styles, operations, operators, machines and balance runs from the
external Apparel Line Balancing API (FastAPI) into Odoo, and exposes
hooks to push the latest applied balance back to MRP work-orders.

* lb.config        — endpoint URL + JWT token
* lb.client        — small REST client (search_read / external-ids)
* lb.style         — local mirror of styles
* lb.operation     — local mirror of operations (linked to mrp.routing.workcenter)
* lb.operator      — operators (linked to hr.employee)
* lb.machine       — machines (linked to mrp.workcenter)
* lb.balance.run   — balance runs (links to mrp.production)
* Cron every 15 min calls lb_sync.sync_all()
""",
    "version": "18.0.1.0.0",
    "author": "Apparel Line Balancing",
    "website": "https://github.com/stephennkihara-a11y/line_balancing",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "depends": ["base", "mrp", "hr"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/lb_config_views.xml",
        "views/lb_balance_run_views.xml",
        "wizards/lb_sync_wizard_views.xml",
    ],
    "application": True,
    "installable": True,
}
