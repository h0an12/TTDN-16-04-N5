# -*- coding: utf-8 -*-
from odoo import fields, models


class MtdnAsset(models.Model):
    _inherit = "mtdn.asset"

    maintenance_request_count = fields.Integer(
        string="Phiếu bảo trì",
        compute="_compute_maintenance_request_count",
        store=False,
    )

    def _compute_maintenance_request_count(self):
        Req = self.env["mtdn.maintenance.request"]
        for rec in self:
            rec.maintenance_request_count = Req.search_count(
                [("request_for", "=", "asset"), ("asset_id", "=", rec.id)]
            )

    def action_view_maintenance_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Phiếu bảo trì",
            "res_model": "mtdn.maintenance.request",
            "view_mode": "list,form",
            "domain": [("request_for", "=", "asset"), ("asset_id", "=", self.id)],
            "context": {"default_request_for": "asset", "default_asset_id": self.id},
        }
