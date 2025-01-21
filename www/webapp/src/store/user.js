import {defineStore} from 'pinia';


export const useUserStore = defineStore('user', {
    state: () => ({
        authenticated: false,
        token: {},
        work_count: 0,
        alerts: [],
        component_args: {},
    }),
    getters: {
        working: state => !!state.work_count,
        component_arg: state => {
            return (componentName) => state.component_args[componentName];
        },
    },
    actions: {
        login(token) {
            this.authenticated = true;
            this.token = token;
        },
        logout() {
            this.authenticated = false;
            this.token = {};
        },
        changeWork(working = true) {
            this.work_count += working ? 1 : -1;
        },
        updateComponentArg(componentName, value) {
            this.component_args[componentName] = value;
        },
        alert(alert) {
            for (const known_alert of this.alerts) {
                if(alert.id === known_alert.id) {
                    return;
                }
            }
            this.alerts.push(alert);
        },
        unalert(id) {
            let del_idx = undefined;
            for (const [idx, alert] of this.alerts.entries()) {
                if(alert.id === id) {
                    del_idx = idx;
                    break;
                }
            }
            if(del_idx !== undefined) {
                this.alerts.splice(del_idx, 1);
            }
        },
    },
});
