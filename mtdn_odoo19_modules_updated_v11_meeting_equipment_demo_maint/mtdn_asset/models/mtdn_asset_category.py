# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MtdnAssetCategory(models.Model):
    _name = "mtdn.asset.category"
    _description = "MTDN Asset Category"
    _order = "name"

    name = fields.Char(string="Tên loại tài sản", required=True, index=True)
    code = fields.Char(string="Mã loại", required=True, index=True, copy=False)

    # Depreciation settings (3 methods + flexible period unit)
    depreciation_method = fields.Selection(
        selection=[
            ("none", "Không khấu hao"),
            ("linear", "Đường thẳng"),
            ("declining", "Số dư giảm dần"),
            ("syd", "Tổng số năm (SYD)"),
        ],
        string="Phương pháp khấu hao",
        required=True,
        default="linear",
        index=True,
        help="Cấu hình khấu hao mặc định cho loại tài sản.",
    )

    depreciation_unit = fields.Selection(
        selection=[("month", "Tháng"), ("year", "Năm")],
        string="Đơn vị khấu hao",
        required=True,
        default="year",
        help="Đơn vị của số kỳ khấu hao (tháng hoặc năm).",
    )

    # Keep the original field name for compatibility with existing data/views.
    depreciation_years = fields.Integer(
        string="Số kỳ khấu hao",
        default=3,
        help="Số kỳ khấu hao theo đơn vị đã chọn. Ví dụ: 36 (tháng) hoặc 3 (năm).",
    )

    declining_factor = fields.Float(
        string="Hệ số giảm dần",
        default=2.0,
        help="Dùng cho phương pháp số dư giảm dần (mặc định 2.0 = double-declining).",
    )

    # Quantities (roll-up from assets)
    asset_ids = fields.One2many("mtdn.asset", "category_id", string="Tài sản")
    quantity_total = fields.Integer(
        string="Tổng số lượng",
        compute="_compute_quantity_total",
        store=True,
        readonly=True,
    )

    active = fields.Boolean(default=True)
    description = fields.Text(string="Mô tả")

    @api.depends("asset_ids", "asset_ids.quantity")
    def _compute_quantity_total(self):
        for rec in self:
            rec.quantity_total = sum(rec.asset_ids.mapped("quantity"))

    _sql_constraints = [
        ("mtdn_asset_category_code_uniq", "unique(code)", "Mã loại tài sản phải là duy nhất."),
    ]
