# -*- coding: utf-8 -*-
from odoo import fields, models

class MtdnMaintenanceTeam(models.Model):
    _name = "mtdn.maintenance.team"
    _description = "Maintenance Team"
    _order = "name"

    name = fields.Char(string="Đội xử lý", required=True, index=True)
    leader_id = fields.Many2one("res.users", string="Trưởng nhóm", ondelete="set null")
    member_ids = fields.Many2many(
        "res.users",
        "mtdn_maintenance_team_user_rel",
        "team_id",
        "user_id",
        string="Thành viên",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("mtdn_maint_team_name_uniq", "unique(name)", "Tên đội xử lý phải là duy nhất."),
    ]
