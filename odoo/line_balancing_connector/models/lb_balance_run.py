from odoo import fields, models


BALANCE_STATUS = [
    ("DRAFT", "Draft"), ("PROPOSED", "Proposed"),
    ("APPLIED", "Applied"), ("REJECTED", "Rejected"),
]


class LBBalanceRun(models.Model):
    _name = "lb.balance.run"
    _description = "Line Balancing — Run"
    _rec_name = "display_name"
    _order = "captured_at desc, id desc"

    external_id = fields.Integer(required=True, index=True)
    style_id = fields.Many2one("lb.style", ondelete="set null")
    line_external_id = fields.Integer()
    target_output_hour = fields.Integer()
    line_efficiency = fields.Float(digits=(5, 2))
    balance_loss = fields.Float(digits=(5, 2))
    status = fields.Selection(BALANCE_STATUS)
    captured_at = fields.Datetime()
    display_name = fields.Char(compute="_compute_display_name", store=True)

    # Optional binding to a real Odoo MRP production order
    production_id = fields.Many2one(
        "mrp.production",
        string="MRP production order",
        ondelete="set null",
        help="When this run is dispatched to a specific production order.",
    )

    assignment_ids = fields.One2many(
        "lb.balance.assignment", "run_id", string="Assignments",
    )

    _sql_constraints = [
        ("uq_external_id", "unique(external_id)", "external_id must be unique"),
    ]

    def _compute_display_name(self):
        for r in self:
            r.display_name = f"Run #{r.external_id} ({r.status or 'DRAFT'})"


class LBBalanceAssignment(models.Model):
    _name = "lb.balance.assignment"
    _description = "Line Balancing — Run assignment"
    _order = "station"

    external_id = fields.Integer(required=True, index=True)
    run_id = fields.Many2one("lb.balance.run", ondelete="cascade", required=True)
    station = fields.Integer(required=True)
    operator_id = fields.Many2one("lb.operator", ondelete="set null")
    operation_id = fields.Many2one("lb.operation", ondelete="set null")
    machine_id = fields.Many2one("lb.machine", ondelete="set null")
    cycle_time = fields.Float(digits=(8, 3))
    expected_output = fields.Integer()

    _sql_constraints = [
        ("uq_external_id", "unique(external_id)", "external_id must be unique"),
    ]
