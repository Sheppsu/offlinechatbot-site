import { updateSetting, toggleCommand } from "./api.js";

const channel = JSON.parse(document.getElementById("channel-data").innerText);

function updateSettingToggle(elm, value) {
    const cls = value ? "on" : "off";
    elm.setAttribute("class", "setting-toggle "+cls);
    elm.children.item(0).setAttribute("class", "setting-toggle-inner "+cls);
}

let updateSettingTimeout = null;
let updateCommandTimeout = {};

function initSetting(setting) {
    updateSettingToggle(setting, setting.getAttribute("value") === "True")

    if (setting.classList.contains("channel-setting"))
        setting.addEventListener("click", () => {
            const newValue = setting.classList.contains("off");
            updateSettingToggle(setting, newValue);

            if (updateSettingTimeout !== null)
                clearTimeout(updateSettingTimeout);

            updateSettingTimeout = setTimeout(() => {
                updateSetting(channel.id, setting.id, newValue)
                updateSettingTimeout = null;
            }, 1000);
        });
    else
        setting.addEventListener("click", () => {
            const newValue = setting.classList.contains("off");
            updateSettingToggle(setting, newValue);

            const currentTimeout = updateCommandTimeout[setting.id];
            if (currentTimeout !== undefined)
                clearTimeout(currentTimeout)

            updateCommandTimeout[setting.id] = setTimeout(() => {
                toggleCommand(setting.id.substring(4), newValue);
                updateCommandTimeout[setting.id] = undefined;
            }, 1000);
        });
}

export function initSettings() {
    for (const elm of document.getElementsByClassName("setting-toggle")) {
        initSetting(elm);
    }
}
