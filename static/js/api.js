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
    return await handleResp(await fetch("/api/commands/"));
}

export async function updateSetting(channelId, setting, value) {
    return await handleResp(
        await fetch(
            `/api/channels/${channelId}/settings/`, {
                method: "PATCH",
                body: JSON.stringify({
                    setting,
                    value
                }),
                headers: authHeader()
            }
        )
    );
}

export async function toggleCommand(cmdId, enable) {
    return await handleResp(
        await fetch(
            `/api/commands/${cmdId}/`, {
                method: "PATCH",
                body: JSON.stringify({enable}),
                headers: authHeader()
            }
        )
    )
}
