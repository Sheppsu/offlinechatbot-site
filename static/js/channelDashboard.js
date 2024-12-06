import { updateSetting } from "./api.js";

const channel = JSON.parse(document.getElementById("channel-data").innerText);

function updateSettingToggle(elm, value) {
    const cls = value ? "on" : "off";
    elm.setAttribute("class", "setting-toggle "+cls);
    elm.children.item(0).setAttribute("class", "setting-toggle-inner "+cls);
}

let updateSettingTimeout = null;
function initSetting(setting) {
    updateSettingToggle(setting, setting.getAttribute("value") === "True")

    setting.addEventListener("click", () => {
        const newValue = setting.classList.contains("off")
        updateSettingToggle(setting, newValue);

        if (updateSettingTimeout !== null)
            clearTimeout(updateSettingTimeout);
        updateSettingTimeout = setTimeout(updateSetting, 1000, channel.id, setting.id, newValue);
    });
}

export function initSettings() {
    for (const elm of document.getElementsByClassName("setting-toggle")) {
        initSetting(elm);
    }
}
