# -*- coding: utf-8 -*-
{
    "name": "MTDN - Nhân sự (Custom HR)",
    "version": "19.0.1.0.0",
    "summary": "Module nhân sự tự tạo (không dùng hr.employee) cho bài tập lớn Thực tập doanh nghiệp.",
    "category": "MTDN",
    "author": "MTDN",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/sequences.xml",
        "views/mtdn_department_views.xml",
        "views/mtdn_job_views.xml",
        "views/mtdn_employee_views.xml",
        "views/mtdn_hr_actions.xml",
        "views/mtdn_hr_menus.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mtdn_hr/static/src/css/mtdn_hr.css",
            "mtdn_hr/static/src/dashboard/hr_dashboard.js",
            "mtdn_hr/static/src/dashboard/hr_dashboard.xml",
        ],
    },
    "application": True,
    "installable": True,
}
