import { getCommands } from "/static/js/api.js";

const navBar = document.getElementById("navigation-bar");
const cmdContainer = document.getElementById("commands-container");


function createNavItem(name) {
    const item = document.createElement("a");
    item.classList.add("navigation-item");
    item.href = "#"+name;
    item.innerText = name;
    return item;
}

function createCommandText(type, text) {
    let elm;
    if (type === "name") {
        elm = document.createElement("a");
        elm.href = "#"+text;
        elm.id = text;
    } else {
        elm = document.createElement("p");
    }

    elm.classList.add("command-"+type);
    elm.innerText = text;

    return elm;
}

function createArgString(arg) {
    const s = arg.f === null ? arg.n : `-${arg.f} ${arg.n}`;
    return arg.o ? `(${s})` : s;
}

function createUsageString(cmd) {
    return `Usage: !${cmd.name} ` + cmd.args.map(createArgString).join(" ");
}

function createCommand(cmd) {
    const container = document.createElement("div");
    container.classList.add("command");

    container.append(createCommandText("name", cmd.name));

    if (cmd.aliases.length > 0)
        container.append(createCommandText("aliases", "Aliases: "+cmd.aliases.join(", ")));

    const infoContainer = document.createElement("div");
    infoContainer.classList.add("command-info-container");

    infoContainer.append(
        createCommandText("description", cmd.description),
        createCommandText("usage", createUsageString(cmd))
    );

    for (const arg of cmd.args) {
        if (arg.d === null)
            continue

        infoContainer.append(createCommandText("usage", `${arg.n}: ${arg.d}`))
    }

    container.append(infoContainer);

    return container;
}

export function createPage() {
    getCommands().then((cmds) => {
        for (const cmd of cmds.sort((a, b) => a.name.localeCompare(b.name))) {
            navBar.append(createNavItem(cmd.name));
            cmdContainer.append(createCommand(cmd));
        }
    });
}
