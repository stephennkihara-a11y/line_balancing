"""Sync orchestrator: pulls data from the Line Balancing API into Odoo
mirror tables and pushes back external-id mappings so the API can quote
Odoo's identifiers.

Scheduled by `data/ir_cron.xml` every 15 minutes; can also be invoked
manually via the `lb.sync.wizard`.
"""
from __future__ import annotations

import logging
from datetime import datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LBSync(models.AbstractModel):
    _name = "lb.sync"
    _description = "Line Balancing — sync orchestrator"

    # ---------- Public entry points -------------------------------------
    @api.model
    def sync_all(self) -> dict:
        config = self.env["lb.config"].get_active()
        client = self.env["lb.client"]
        summary = {"styles": 0, "operations": 0, "operators": 0,
                   "machines": 0, "balance_runs": 0}
        if config.sync_styles:
            summary["styles"], summary["operations"] = self._sync_styles(client, config)
        if config.sync_operators:
            summary["operators"] = self._sync_operators(client, config)
        if config.sync_machines:
            summary["machines"] = self._sync_machines(client, config)
        if config.sync_balance_runs:
            summary["balance_runs"] = self._sync_balance_runs(client, config)
        config.sudo().write({"last_sync": fields.Datetime.now()})
        _logger.info("Line Balancing sync complete: %s", summary)
        return summary

    # ---------- Helpers --------------------------------------------------
    @api.model
    def _push_external_id(self, client, config, *, entity, local_id, erp_model, erp_id):
        try:
            client.upsert_external_id(
                config, entity=entity, local_id=local_id,
                erp_model=erp_model, erp_id=str(erp_id),
            )
        except Exception:
            _logger.exception("Failed pushing external id for %s/%s", entity, local_id)

    # ---------- Styles + operations --------------------------------------
    @api.model
    def _sync_styles(self, client, config) -> tuple[int, int]:
        styles = client.search_read(config, "lb.style", domain=[], limit=1000)
        n_styles = 0
        n_ops = 0
        Style = self.env["lb.style"]
        Operation = self.env["lb.operation"]
        for s in styles:
            local = Style.search([("external_id", "=", s["id"])], limit=1)
            vals = {
                "external_id": s["id"],
                "style_code": s.get("style_code"),
                "name": s.get("name"),
                "garment_type": s.get("garment_type"),
                "total_sam": float(s.get("total_sam") or 0),
                "description": s.get("description"),
                "last_sync": fields.Datetime.now(),
            }
            if local:
                local.write(vals)
            else:
                local = Style.create(vals)
            n_styles += 1
            self._push_external_id(
                client, config, entity="style", local_id=s["id"],
                erp_model=Style._name, erp_id=local.id,
            )

            # Operations
            ops = client.search_read(
                config, "lb.operation", domain=[["style_id", "=", s["id"]]], limit=2000,
            )
            for op in ops:
                op_local = Operation.search([("external_id", "=", op["id"])], limit=1)
                op_vals = {
                    "external_id": op["id"],
                    "style_id": local.id,
                    "op_code": op.get("op_code"),
                    "sequence": op.get("sequence") or 0,
                    "description": op.get("description"),
                    "sam": float(op.get("sam") or 0),
                    "machine_type": op.get("machine_type"),
                    "skill_level": op.get("skill_level") or 1,
                    "section": op.get("section"),
                }
                if op_local:
                    op_local.write(op_vals)
                else:
                    op_local = Operation.create(op_vals)
                n_ops += 1
                self._push_external_id(
                    client, config, entity="operation", local_id=op["id"],
                    erp_model=Operation._name, erp_id=op_local.id,
                )
        return n_styles, n_ops

    @api.model
    def _sync_operators(self, client, config) -> int:
        rows = client.search_read(config, "lb.operator", domain=[], limit=2000)
        Operator = self.env["lb.operator"]
        n = 0
        for o in rows:
            local = Operator.search([("external_id", "=", o["id"])], limit=1)
            vals = {
                "external_id": o["id"],
                "employee_code": o.get("employee_code"),
                "name": o.get("name"),
                "grade": o.get("grade") or 1,
                "base_efficiency": float(o.get("base_efficiency") or 0),
                "attendance_status": o.get("attendance_status") or "PRESENT",
            }
            if local:
                local.write(vals)
            else:
                local = Operator.create(vals)
            n += 1
            self._push_external_id(
                client, config, entity="operator", local_id=o["id"],
                erp_model=Operator._name, erp_id=local.id,
            )
        return n

    @api.model
    def _sync_machines(self, client, config) -> int:
        rows = client.search_read(config, "lb.machine", domain=[], limit=2000)
        Machine = self.env["lb.machine"]
        n = 0
        for m in rows:
            local = Machine.search([("external_id", "=", m["id"])], limit=1)
            vals = {
                "external_id": m["id"],
                "machine_code": m.get("machine_code"),
                "type": m.get("type"),
                "status": m.get("status") or "IDLE",
                "line_external_id": m.get("line_id"),
                "notes": m.get("notes"),
            }
            if local:
                local.write(vals)
            else:
                local = Machine.create(vals)
            n += 1
            self._push_external_id(
                client, config, entity="machine", local_id=m["id"],
                erp_model=Machine._name, erp_id=local.id,
            )
        return n

    @api.model
    def _sync_balance_runs(self, client, config) -> int:
        rows = client.list_balance_runs(config) or []
        Run = self.env["lb.balance.run"]
        Assign = self.env["lb.balance.assignment"]
        n = 0
        for r in rows:
            run_local = Run.search([("external_id", "=", r["id"])], limit=1)
            style = self.env["lb.style"].search(
                [("external_id", "=", r.get("style_id"))], limit=1,
            )
            captured = r.get("created_at")
            captured_dt = (
                datetime.fromisoformat(captured.replace("Z", "+00:00"))
                if isinstance(captured, str) else fields.Datetime.now()
            )
            vals = {
                "external_id": r["id"],
                "style_id": style.id if style else False,
                "line_external_id": r.get("line_id"),
                "target_output_hour": r.get("target_output_hour") or 0,
                "line_efficiency": float(r.get("line_efficiency") or 0),
                "balance_loss": float(r.get("balance_loss") or 0),
                "status": r.get("status"),
                "captured_at": captured_dt,
            }
            if run_local:
                run_local.write(vals)
            else:
                run_local = Run.create(vals)
            n += 1
            self._push_external_id(
                client, config, entity="balance_run", local_id=r["id"],
                erp_model=Run._name, erp_id=run_local.id,
            )

            # Pull full layout (assignments)
            full = client.get_balance_run(config, r["id"])
            for a in (full or {}).get("assignments", []):
                operator = self.env["lb.operator"].search(
                    [("external_id", "=", a.get("operator_id"))], limit=1,
                )
                operation = self.env["lb.operation"].search(
                    [("external_id", "=", a.get("operation_id"))], limit=1,
                )
                machine = self.env["lb.machine"].search(
                    [("external_id", "=", a.get("machine_id"))], limit=1,
                )
                # Use synthetic external_id = run_id*100000 + station for stability
                synth = r["id"] * 100000 + int(a["station"])
                local = Assign.search([("external_id", "=", synth)], limit=1)
                a_vals = {
                    "external_id": synth,
                    "run_id": run_local.id,
                    "station": a["station"],
                    "operator_id": operator.id if operator else False,
                    "operation_id": operation.id if operation else False,
                    "machine_id": machine.id if machine else False,
                    "cycle_time": float(a.get("cycle_time") or 0),
                    "expected_output": a.get("expected_output") or 0,
                }
                if local:
                    local.write(a_vals)
                else:
                    Assign.create(a_vals)
        return n
