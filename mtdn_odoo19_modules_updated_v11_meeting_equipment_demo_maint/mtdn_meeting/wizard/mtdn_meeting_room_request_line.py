# -*- coding: utf-8 -*-

from odoo import fields, models


class MtdnMeetingRoomRequestLine(models.TransientModel):
    _name = "mtdn.meeting.room.request.line"
    _description = "MTDN Meeting Room Request - Suggested Rooms"

    request_id = fields.Many2one(
        "mtdn.meeting.room.request",
        string="Yêu cầu",
        required=True,
        ondelete="cascade",
    )
    room_id = fields.Many2one(
        "mtdn.meeting.room",
        string="Phòng",
        required=True,
        ondelete="restrict",
    )

    # Related fields for nicer list display
    code = fields.Char(related="room_id.code", readonly=True)
    name = fields.Char(related="room_id.name", readonly=True)
    location = fields.Char(related="room_id.location", readonly=True)
    capacity = fields.Integer(related="room_id.capacity", readonly=True)
    state = fields.Selection(related="room_id.state", readonly=True)


    ai_rank = fields.Integer(string="AI Rank", readonly=True)
    ai_reason = fields.Char(string="Lý do (AI)", readonly=True)

    equipment_type_summary = fields.Char(
        string="Thiết bị",
        compute="_compute_equipment_type_summary",
        readonly=True,
    )

    def _compute_equipment_type_summary(self):
        for rec in self:
            types = rec.room_id.equipment_type_ids.mapped("name")
            rec.equipment_type_summary = ", ".join(types) if types else "-"

    def action_select_room(self):
        self.ensure_one()
        self.request_id.selected_room_id = self.room_id
        return {
            "type": "ir.actions.act_window",
            "res_model": "mtdn.meeting.room.request",
            "res_id": self.request_id.id,
            "view_mode": "form",
            "target": "new",
        }
