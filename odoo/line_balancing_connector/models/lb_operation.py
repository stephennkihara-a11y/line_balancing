from odoo import fields, models


MACHINE_TYPES = [
    ("SNLS", "SNLS"), ("OL", "OL"), ("FOA", "FOA"),
    ("BARTACK", "Bartack"), ("BUTTON", "Button"),
    ("BUTTONHOLE", "Buttonhole"), ("IRON", "Iron"), ("MANUAL", "Manual"),
]


class LBOperation(models.Model):
    _name = "lb.operation"
    _description = "Line Balancing — Operation"
    _rec_name = "op_code"
    _order = "style_id, sequence"

    external_id = fields.Integer(string="External ID", required=True, index=True)
    style_id = fields.Many2one("lb.style", required=True, ondelete="cascade")
    op_code = fields.Char(required=True)
    sequence = fields.Integer()
    description = fields.Char()
    sam = fields.Float(digits=(8, 3))
    machine_type = fields.Selection(MACHINE_TYPES)
    skill_level = fields.Integer(default=1)
    section = fields.Char()

    # Map onto Odoo MRP routing operation, when applicable
    workcenter_operation_id = fields.Many2one(
        "mrp.routing.workcenter",
        string="MRP routing operation",
        ondelete="set null",
        help="Odoo's routing operation that mirrors this op.",
    )

    _sql_constraints = [
        ("uq_external_id", "unique(external_id)", "external_id must be unique"),
    ]
