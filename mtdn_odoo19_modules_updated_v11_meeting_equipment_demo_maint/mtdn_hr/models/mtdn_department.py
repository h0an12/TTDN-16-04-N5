# -*- coding: utf-8 -*-
from odoo import fields, models


class MtdnDepartment(models.Model):
    _name = "mtdn.department"
    _description = "MTDN Department"
    _order = "name"

    name = fields.Char(string="Tên phòng ban", required=True, index=True)
    code = fields.Char(string="Mã phòng ban", required=True, index=True, copy=False)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    manager_id = fields.Many2one(
        "mtdn.employee",
        string="Trưởng phòng",
        ondelete="set null",
    )

    description = fields.Text(string="Mô tả")

    employee_ids = fields.One2many("mtdn.employee", "department_id", string="Nhân viên")

    _sql_constraints = [
        ("mtdn_department_code_company_uniq", "unique(code, company_id)", "Mã phòng ban phải là duy nhất trong mỗi công ty."),
    ]
