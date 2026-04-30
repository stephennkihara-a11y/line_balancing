from odoo import fields, models

from .lb_operation import MACHINE_TYPES


MACHINE_STATUS = [
    ("WORKING", "Working"),
    ("IDLE", "Idle"),
    ("BREAKDOWN", "Breakdown"),
    ("MAINTENANCE", "Maintenance"),
]


class LBMachine(models.Model):
    _name = "lb.machine"
    _description = "Line Balancing — Machine"
    _rec_name = "machine_code"
    _order = "machine_code"

    external_id = fields.Integer(required=True, index=True)
    machine_code = fields.Char(required=True, index=True)
    type = fields.Selection(MACHINE_TYPES, required=True)
    status = fields.Selection(MACHINE_STATUS, default="IDLE")
    line_external_id = fields.Integer()
    notes = fields.Char()

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="MRP work-center",
        ondelete="set null",
        help="Odoo work-center this machine maps to.",
    )

    _sql_constraints = [
        ("uq_external_id", "unique(external_id)", "external_id must be unique"),
    ]
