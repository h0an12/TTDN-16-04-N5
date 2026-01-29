# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MtdnBranch(models.Model):
    _name = "mtdn.branch"
    _description = "MTDN Branch"
    _order = "code, name"

    code = fields.Char(string="Mã chi nhánh", required=True, index=True, copy=False)
    name = fields.Char(string="Tên chi nhánh", required=True, index=True)

    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Địa chỉ/Đối tác",
        help="Đối tác/địa chỉ đại diện của chi nhánh (tùy chọn).",
        ondelete="set null",
    )

    active = fields.Boolean(default=True)
    description = fields.Text(string="Mô tả")

    asset_ids = fields.One2many("mtdn.asset", "branch_id", string="Tài sản")
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
        ("mtdn_branch_code_company_uniq", "unique(code, company_id)", "Mã chi nhánh phải là duy nhất trong mỗi công ty."),
    ]
