# -*- coding: utf-8 -*-

from odoo import fields, models


class MtdnMeetingAiConfig(models.Model):
    _name = "mtdn.meeting.ai.config"
    _description = "MTDN Meeting AI Configuration"
    _rec_name = "name"

    name = fields.Char(string="Tên cấu hình", required=True, default="Gemini")
    active = fields.Boolean(default=True)

    api_key = fields.Char(string="Gemini API Key", password=True, help="API Key lấy từ Google AI Studio.")
    model_name = fields.Char(
        string="Model",
        required=True,
        default="gemini-2.5-flash",
        help="Ví dụ: gemini-2.5-flash, gemini-2.5-pro, gemini-3-flash-preview...",
    )
    note = fields.Text(string="Ghi chú")

    def get_active_config(self):
        """Return the first active config (admin-managed)."""
        return self.search([("active", "=", True)], limit=1)
