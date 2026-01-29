# -*- coding: utf-8 -*-
{
    "name": "MTDN - Phòng họp (Meeting Room Booking)",
    "version": "19.0.1.0.0",
    "summary": "Quản lý phòng họp & đặt lịch, gợi ý phòng theo yêu cầu.",
    "category": "MTDN",
    "author": "MTDN",
    "license": "LGPL-3",
    "depends": ["base", "web", "mtdn_hr", "mtdn_asset"],
    "data": [
        "security/ir.model.access.csv",
        "data/seed_rooms.xml",
        "views/mtdn_meeting_room_views.xml",
        "views/mtdn_meeting_booking_views.xml",
        "views/mtdn_meeting_room_request_views.xml",
        "views/mtdn_meeting_ai_assistant_views.xml",
        "views/mtdn_meeting_booking_time_wizard_views.xml",
        "views/mtdn_meeting_actions.xml",
        "views/mtdn_meeting_ai_config_views.xml",
        "views/mtdn_meeting_menus.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "application": True,
    "installable": True,
}
