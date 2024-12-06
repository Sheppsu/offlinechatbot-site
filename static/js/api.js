async function handleResp(resp) {
    const data = await resp.json();
    if ("error" in data) {
        console.log(`Failed request to ${resp.url}: ${data.error}`);
        return undefined;
    } else {
        return data.data;
    }
}

function getCSRFToken() {
    for (const [k, v] of document.cookie.split(";").map((item) => item.split("="))) {
        if (k === "csrftoken") {
            return v;
        }
    }
}

function authHeader() {
    return {
        "X-CSRFToken": getCSRFToken()
    }
}

export async function getCommands() {
    const resp = await fetch("/api/commands/");
    return await handleResp(resp);
}

export async function updateSetting(channelId, setting, value) {
    const resp = await fetch(
        `/api/channels/${channelId}/settings/`, {
            method: "PATCH",
            body: JSON.stringify({
                setting,
                value
            }),
            headers: authHeader()
        }
    )
    return await handleResp(resp);
}
