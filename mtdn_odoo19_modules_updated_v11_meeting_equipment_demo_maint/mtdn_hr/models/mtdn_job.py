# -*- coding: utf-8 -*-
from odoo import fields, models


class MtdnJob(models.Model):
    _name = "mtdn.job"
    _description = "MTDN Job Position"
    _order = "name"

    name = fields.Char(string="Tên chức danh", required=True, index=True)
    code = fields.Char(string="Mã chức danh", required=True, index=True, copy=False)
    department_id = fields.Many2one(
        "mtdn.department",
        string="Phòng ban",
        required=True,
        ondelete="restrict",
        index=True,
        help="Mỗi phòng ban có danh sách chức danh riêng.",
    )
    company_id = fields.Many2one(
        related="department_id.company_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string="Mô tả")

    _sql_constraints = [
        (
            "mtdn_job_code_department_uniq",
            "unique(code, department_id)",
            "Mã chức danh phải là duy nhất trong mỗi phòng ban.",
        ),
    ]
