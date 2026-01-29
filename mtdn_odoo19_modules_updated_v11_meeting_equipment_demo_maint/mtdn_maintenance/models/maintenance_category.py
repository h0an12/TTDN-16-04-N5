# -*- coding: utf-8 -*-
from odoo import fields, models

class MtdnMaintenanceCategory(models.Model):
    _name = "mtdn.maintenance.category"
    _description = "Maintenance Category"
    _order = "name"

    name = fields.Char(string="Loại sự cố", required=True, index=True)
    description = fields.Text(string="Mô tả")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("mtdn_maint_cat_name_uniq", "unique(name)", "Loại sự cố phải là duy nhất."),
    ]
