export async function getCommands() {
    const resp = await fetch("/api/commands/");
    return (await resp.json()).data;
}
