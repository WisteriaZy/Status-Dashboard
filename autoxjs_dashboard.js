/*
autoxjs_dashboard.js - 适配 Local Device Status Dashboard
使用 Autox.js 编写的安卓自动更新状态脚本
*/

// ========== 配置 ==========
const API_URL = 'https://status.wisteriazy.moe/device/set'; // API 地址
const SECRET = 'erh3PVxATcxS9qHlVZkAXBf_TZ6f-HrcGwNPREOJ-bc'; // 从 config/device_secret.txt 获取
const ID = 'phone'; // 设备唯一 ID
const SHOW_NAME = '手机'; // 显示名称
const CHECK_INTERVAL = 3000; // 状态变化时的检查间隔 (毫秒)
const HEARTBEAT_INTERVAL = 10000; // 状态不变时的心跳间隔 (毫秒)
// ===========================

auto.waitFor();

function log(msg) {
    try {
        console.log(`[dashboard] ${msg.replace(SECRET, '[SECRET]')}`);
    } catch (e) {
        console.log(`[dashboard] ${msg}`);
    }
}

var last_status = '';
var last_send_time = 0;

function check_status() {
    if (!device.isScreenOn()) {
        return '';
    }
    var app_package = currentPackage();
    var app_name = app.getAppName(app_package);
    var battery = device.getBattery();

    if (device.isCharging()) {
        var retname = `[${battery}% +] ${app_name}`;
    } else {
        var retname = `[${battery}%] ${app_name}`;
    }
    if (!app_name) {
        retname = '';
    }
    return retname;
}

function do_send(app_name) {
    var using = app_name !== '';

    log(`POST ${API_URL}`);
    try {
        var r = http.postJson(API_URL, {
            'secret': SECRET,
            'id': ID,
            'show_name': SHOW_NAME,
            'using': using,
            'app_name': app_name
        });
        log(`response: ${r.body.string()}`);
        last_send_time = Date.now();
    } catch (e) {
        log(`ERROR: ${e}`);
    }
}

function send_status() {
    var app_name = check_status();
    var now = Date.now();

    if (app_name !== last_status) {
        // 状态变化，立即发送
        log(`status changed: '${app_name}'`);
        last_status = app_name;
        do_send(app_name);
    } else if (now - last_send_time >= HEARTBEAT_INTERVAL) {
        // 状态不变但超过心跳间隔，发送心跳
        log(`heartbeat: '${app_name}'`);
        do_send(app_name);
    } else {
        // 状态不变且未到心跳时间，跳过
        log('same status, waiting for heartbeat');
    }
}

events.on("exit", function () {
    log("Script exit, reporting offline");
    toast("[dashboard] 脚本停止");
    try {
        http.postJson(API_URL, {
            'secret': SECRET,
            'id': ID,
            'show_name': SHOW_NAME,
            'using': false,
            'app_name': ''
        });
    } catch (e) {
        log(`Exit report error: ${e}`);
    }
});

while (true) {
    try {
        send_status();
    } catch (e) {
        log(`ERROR: ${e}`);
    }
    sleep(CHECK_INTERVAL);
}
