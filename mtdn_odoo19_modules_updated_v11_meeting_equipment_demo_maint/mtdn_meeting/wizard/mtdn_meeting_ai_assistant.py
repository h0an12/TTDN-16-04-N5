# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import ValidationError


class MtdnMeetingAIAssistant(models.TransientModel):
    _name = "mtdn.meeting.ai.assistant"
    _description = "MTDN Meeting - AI Assistant (Gemini)"

    request_text = fields.Text(
        string="Yêu cầu",
        required=True,
        help="Nhập yêu cầu đặt phòng bằng tiếng Việt. VD: Mai 9h–10h họp 8 người, cần TV và zoom.",
    )

    def action_parse_and_open_request(self):
        """Parse request_text using existing Gemini parser, then open the standard room request wizard."""
        self.ensure_one()
        if not (self.request_text or "").strip():
            raise ValidationError("Vui lòng nhập yêu cầu để AI phân tích.")

        # Create the standard room request wizard and reuse its parsing logic
        req = self.env["mtdn.meeting.room.request"].create({
            "ai_request_text": self.request_text,
        })
        return req.action_ai_parse()
