from odoo import fields, models


ATTENDANCE = [("PRESENT", "Present"), ("ABSENT", "Absent"), ("LEAVE", "Leave")]


class LBOperator(models.Model):
    _name = "lb.operator"
    _description = "Line Balancing — Operator"
    _rec_name = "name"
    _order = "employee_code"

    external_id = fields.Integer(required=True, index=True)
    employee_code = fields.Char(required=True)
    name = fields.Char(required=True)
    grade = fields.Integer()
    base_efficiency = fields.Float(digits=(5, 2))
    attendance_status = fields.Selection(ATTENDANCE)

    employee_id = fields.Many2one(
        "hr.employee",
        string="HR employee",
        ondelete="set null",
        help="Odoo employee record this operator is bound to.",
    )

    _sql_constraints = [
        ("uq_external_id", "unique(external_id)", "external_id must be unique"),
    ]
