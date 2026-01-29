# -*- coding: utf-8 -*-

from odoo import fields, models


class MtdnMeetingRoomRequestAlt(models.TransientModel):
    _name = "mtdn.meeting.room.request.alt"
    _description = "MTDN Meeting Room Request - AI Alternative Time"

    request_id = fields.Many2one(
        "mtdn.meeting.room.request",
        string="Yêu cầu",
        required=True,
        ondelete="cascade",
    )
    start_datetime = fields.Datetime(string="Bắt đầu", required=True)
    end_datetime = fields.Datetime(string="Kết thúc", required=True)
    reason = fields.Char(string="Lý do (AI)", readonly=True)

    def action_apply_alternative(self):
        self.ensure_one()
        req = self.request_id
        req.start_datetime = self.start_datetime
        req.end_datetime = self.end_datetime
        # re-run search to refresh suggested rooms
        return req.action_search_rooms()
