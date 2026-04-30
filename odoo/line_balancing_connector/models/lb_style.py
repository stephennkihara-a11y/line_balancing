from odoo import fields, models


class LBStyle(models.Model):
    _name = "lb.style"
    _description = "Line Balancing — Style"
    _rec_name = "name"
    _order = "style_code"

    external_id = fields.Integer(string="External ID", required=True, index=True)
    style_code = fields.Char(string="Style code", required=True, index=True)
    name = fields.Char(required=True)
    garment_type = fields.Char()
    total_sam = fields.Float(string="Total SAM (min)", digits=(10, 3))
    description = fields.Text()
    operation_ids = fields.One2many("lb.operation", "style_id", string="Operations")
    last_sync = fields.Datetime()

    _sql_constraints = [
        ("uq_external_id", "unique(external_id)", "external_id must be unique"),
    ]
