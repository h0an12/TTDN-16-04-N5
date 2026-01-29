# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MtdnAssetEquipmentType(models.Model):
    _name = "mtdn.asset.equipment.type"
    _description = "MTDN Meeting Equipment Type"
    _order = "name"

    name = fields.Char(string="Tên loại thiết bị", required=True, index=True)
    code = fields.Char(string="Mã loại", required=True, index=True, copy=False)
    active = fields.Boolean(default=True)
    description = fields.Text(string="Mô tả")

    asset_ids = fields.One2many("mtdn.asset", "equipment_type_id", string="Tài sản")
    quantity_total = fields.Integer(
        string="Tổng số lượng",
        compute="_compute_quantity_total",
        store=True,
        readonly=True,
    )

    @api.depends("asset_ids", "asset_ids.quantity")
    def _compute_quantity_total(self):
        for rec in self:
            rec.quantity_total = sum(rec.asset_ids.mapped("quantity"))

    _sql_constraints = [
        (
            "mtdn_asset_equipment_type_code_uniq",
            "unique(code)",
            "Mã loại thiết bị phải là duy nhất.",
        ),
    ]
