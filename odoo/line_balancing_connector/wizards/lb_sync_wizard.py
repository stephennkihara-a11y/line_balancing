from odoo import fields, models


class LBSyncWizard(models.TransientModel):
    _name = "lb.sync.wizard"
    _description = "Line Balancing — manual sync wizard"

    summary = fields.Text(readonly=True)

    def action_sync(self):
        result = self.env["lb.sync"].sync_all()
        self.summary = (
            f"Synced styles={result['styles']} ops={result['operations']} "
            f"operators={result['operators']} machines={result['machines']} "
            f"runs={result['balance_runs']}"
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
