/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class MtdnHrDashboard extends Component {
    static template = "mtdn_hr.dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            employee_total: 0,
            probation: 0,
            working: 0,
            on_leave: 0,
            resigned: 0,
            department_total: 0,
            job_total: 0,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        const data = await this.orm.call("mtdn.employee", "mtdn_get_dashboard_data", []);
        Object.assign(this.state, data);
        this.state.loading = false;
    }

    _openWindowAction({ name, res_model, domain }) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model,
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            domain: domain || [],
            context: { active_test: false },
        });
    }

    openAllEmployees() {
        this._openWindowAction({ name: "Nhân viên", res_model: "mtdn.employee", domain: [] });
    }

    openProbationEmployees() {
        this._openWindowAction({
            name: "Nhân viên - Thử việc",
            res_model: "mtdn.employee",
            domain: [["state", "=", "probation"]],
        });
    }

    openWorkingEmployees() {
        this._openWindowAction({
            name: "Nhân viên - Đang làm",
            res_model: "mtdn.employee",
            domain: [["state", "=", "working"]],
        });
    }

    openOnLeaveEmployees() {
        this._openWindowAction({
            name: "Nhân viên - Tạm nghỉ",
            res_model: "mtdn.employee",
            domain: [["state", "=", "on_leave"]],
        });
    }

    openResignedEmployees() {
        this._openWindowAction({
            name: "Nhân viên - Nghỉ việc",
            res_model: "mtdn.employee",
            domain: [["state", "=", "resigned"]],
        });
    }

    openDepartments() {
        this._openWindowAction({ name: "Phòng ban", res_model: "mtdn.department", domain: [] });
    }

    openJobs() {
        this._openWindowAction({ name: "Chức danh", res_model: "mtdn.job", domain: [] });
    }
}

registry.category("actions").add("mtdn_hr.dashboard", MtdnHrDashboard);

export default MtdnHrDashboard;
