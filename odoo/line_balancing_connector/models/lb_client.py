"""Tiny HTTP client wrapping the Line Balancing FastAPI endpoints.

Public methods:
    login()                      -> refreshes self.access_token
    search_read(model, domain, fields=None, limit=200)
    propose_external_id(entity, local_id, erp_model, erp_id)
    get_balance_run(run_id)
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests
from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LBClient(models.AbstractModel):
    """Helper sitting under `lb.config`. Stateless from Odoo's perspective —
    the `config` record is passed into each call.
    """
    _name = "lb.client"
    _description = "Line Balancing — REST client"

    # ---------- low-level ------------------------------------------------
    @api.model
    def _request(self, config, method: str, path: str, *, json_body=None, params=None):
        if not config.access_token:
            self._login(config)
        url = f"{config.base_url.rstrip('/')}/api{path}"
        headers = {
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        }
        try:
            r = requests.request(
                method, url, headers=headers, params=params,
                data=json.dumps(json_body) if json_body is not None else None,
                timeout=30,
            )
        except requests.RequestException as e:
            raise UserError(f"Line Balancing API unreachable: {e}") from e

        if r.status_code == 401:
            # Token expired — try one refresh
            self._login(config)
            headers["Authorization"] = f"Bearer {config.access_token}"
            r = requests.request(
                method, url, headers=headers, params=params,
                data=json.dumps(json_body) if json_body is not None else None,
                timeout=30,
            )
        if not r.ok:
            raise UserError(f"{method} {path} failed: {r.status_code} {r.text}")
        if r.status_code == 204 or not r.content:
            return None
        return r.json()

    @api.model
    def _login(self, config):
        url = f"{config.base_url.rstrip('/')}/api/auth/login"
        try:
            r = requests.post(
                url,
                json={"username": config.username, "password": config.password or ""},
                timeout=15,
            )
        except requests.RequestException as e:
            raise UserError(f"Could not reach login endpoint: {e}") from e
        if not r.ok:
            raise UserError(f"Login failed ({r.status_code}): {r.text}")
        config.sudo().write({"access_token": r.json()["access_token"]})

    # ---------- high-level ----------------------------------------------
    @api.model
    def search_read(
        self, config, model: str, domain: list | None = None,
        fields: list[str] | None = None, limit: int = 200, offset: int = 0,
    ) -> list[dict[str, Any]]:
        body = {
            "model": model,
            "domain": domain or [],
            "fields": fields,
            "limit": limit,
            "offset": offset,
        }
        resp = self._request(config, "POST", "/odoo/search_read", json_body=body)
        return resp.get("records", []) if resp else []

    @api.model
    def upsert_external_id(
        self, config, *, entity: str, local_id: int, erp_model: str, erp_id: str,
    ) -> dict[str, Any]:
        body = {
            "entity": entity,
            "local_id": local_id,
            "erp_model": erp_model,
            "erp_id": erp_id,
        }
        return self._request(config, "POST", "/odoo/external-ids", json_body=body)

    @api.model
    def get_balance_run(self, config, run_id: int) -> dict[str, Any]:
        return self._request(config, "GET", f"/balance/runs/{run_id}")

    @api.model
    def list_balance_runs(self, config, line_id: int | None = None) -> list[dict]:
        params = {"line_id": line_id} if line_id else None
        return self._request(config, "GET", "/balance/runs", params=params) or []
