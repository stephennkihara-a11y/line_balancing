from odoo import api, fields, models


class LBConfig(models.Model):
    """Singleton-style record holding endpoint + credentials.

    Stored in `ir.config_parameter` would also work but a dedicated model
    makes it easier to expose a config form in Odoo's UI and audit changes.
    """
    _name = "lb.config"
    _description = "Line Balancing — connector config"
    _rec_name = "base_url"

    base_url = fields.Char(
        string="API base URL",
        required=True,
        default="http://localhost:8000",
        help="Root URL of the Line Balancing FastAPI service (no trailing /api).",
    )
    username = fields.Char(string="Username", required=True, default="admin")
    password = fields.Char(string="Password", required=False)
    access_token = fields.Char(
        string="Access token",
        readonly=True,
        help="Last successfully obtained JWT. Refreshed by login() automatically.",
    )
    last_sync = fields.Datetime(string="Last sync at", readonly=True)
    sync_styles = fields.Boolean(default=True)
    sync_operators = fields.Boolean(default=True)
    sync_machines = fields.Boolean(default=True)
    sync_balance_runs = fields.Boolean(default=True)
    enabled = fields.Boolean(default=True)

    @api.model
    def get_active(self):
        rec = self.search([("enabled", "=", True)], limit=1)
        if not rec:
            raise self.env["odoo.exceptions"].UserError(
                "No active Line Balancing config — create one under "
                "Manufacturing › Line Balancing › Settings."
            )
        return rec
