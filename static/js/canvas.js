// constants

const colors = [[255, 255, 255], [204, 204, 204], [153, 153, 153], [102, 102, 102],
    [51, 51, 51], [0, 0, 0], [255, 0, 0], [255, 51, 0], [255, 102, 0],
    [255, 153, 0], [255, 204, 0], [255, 255, 0], [204, 255, 0], [153, 255, 0],
    [102, 255, 0], [51, 255, 0], [0, 255, 0], [0, 255, 51], [0, 255, 102],
    [0, 255, 153], [0, 255, 204], [0, 255, 255], [0, 204, 255], [0, 153, 255],
    [0, 102, 255], [0, 51, 255], [0, 0, 255], [51, 0, 255], [102, 0, 255],
    [153, 0, 255], [204, 0, 255], [255, 0, 255], [255, 0, 204], [255, 0, 153],
    [255, 0, 102], [150, 75, 0], [176, 126, 65], [224, 182, 114], [255, 224, 163],
	[255, 234, 209]];
const hexColors = ['#ffffff', '#cccccc', '#999999', '#666666', '#333333', '#000000',
    '#ff0000', '#ff3300', '#ff6600', '#ff9900', '#ffcc00', '#ffff00', '#ccff00',
    '#99ff00', '#66ff00', '#33ff00', '#00ff00', '#00ff33', '#00ff66', '#00ff99',
    '#00ffcc', '#00ffff', '#00ccff', '#0099ff', '#0066ff', '#0033ff', '#0000ff',
    '#3300ff', '#6600ff', '#9900ff', '#cc00ff', '#ff00ff', '#ff00cc', '#ff0099',
    '#ff0066', '#964b00', '#b07e41', '#e0b672', '#ffe0a3', '#ffead1'];

// elements

const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const canvasContainer = document.getElementById("canvas-container");
const placePosLabel = document.getElementById("place-pos-label");
const moveDiv = document.getElementById("canvas-move-container");
moveDiv.style.transform = "translate(0px, 0px)";
const zoomDiv = document.getElementById("canvas-zoom-container");
zoomDiv.style.transform = "scale(1, 1)";
const colorPicker = document.getElementById("color-picker");
const zooms = document.querySelectorAll(".zoom-option");
const colorOptions = document.querySelectorAll(".color-option");
const guis = document.querySelectorAll(".gui");
const placeButton = document.getElementById("place-button");
const placeLabel = document.getElementById("place-label");
const placeOutline = document.getElementById("place-outline");
const userLabel = document.getElementById("user-label");
const clearButton = document.getElementById("clear-button");
const clearX1 = document.getElementById("clear-x1");
const clearY1 = document.getElementById("clear-y1");
const clearX2 = document.getElementById("clear-x2");
const clearY2 = document.getElementById("clear-y2");
const banButton = document.getElementById("ban-button");
const banInput = document.getElementById("ban-input");
const cooldownButton = document.getElementById("cooldown-button");
const cooldownInput = document.getElementById("cooldown-input");
const errorBox = document.getElementById("error-container");
const errorLabel = document.getElementById("error-label");

const canvasWidth = 750;
const canvasHeight = 750;

// states

var ws = null;
var isAuthenticated = false;
var currentlySelectedColor = 0;
var pressed = false;
var mousePos = [0, 0];
var currentZoom = null;
var currentZoomAmount = 1;
var userList = [];
var onCooldown = false;
var scrollAmount = 0;

// canvas drawing

function loadCanvas(data) {
    const view = new Uint8Array(data);
    const pixels = new Uint8ClampedArray(view.length*4);
    for (var i=0; i<view.length; i++) {
        const color = colors[view[i]];
        const index = i*4;
        pixels[index] = color[0];
        pixels[index+1] = color[1];
        pixels[index+2] = color[2];
        pixels[index+3] = 255;
    }
    const imageData = new ImageData(pixels, canvasWidth, canvasHeight);
    ctx.putImageData(imageData, 0, 0);
}

function placePixel(user, x, y, c) {
    ctx.fillStyle = hexColors[c];
    ctx.fillRect(x, y, 1, 1);
    userList[x + canvasWidth * y] = user;
    updatePlaceOutline();
}

function clearCanvas(x1, y1, x2, y2) {
    ctx.fillStyle = hexColors[0];
    ctx.fillRect(x1, y1, x2-x1+1, y2-y1+1);
}

function getPlacePos(canvasRect = null) {
    const containerRect = canvasContainer.getBoundingClientRect();
    if (canvasRect === null) {
        canvasRect = canvas.getBoundingClientRect();
    }
    const x = canvasWidth * ((containerRect.left + containerRect.right) / 2 - canvasRect.left) / canvasRect.width;
    const y = canvasHeight * ((containerRect.top + containerRect.bottom) / 2 - canvasRect.top) / canvasRect.height;
    return [x, y];
}

function getClearPos() {
    const x1 = parseInt(clearX1.value);
    const y1 = parseInt(clearY1.value);
    const x2 = parseInt(clearX2.value);
    const y2 = parseInt(clearY2.value);
    return [x1, y1, x2, y2];
}

function resetClearPos() {
    clearX1.value = "";
    clearY1.value = "";
    clearX2.value = "";
    clearY2.value = "";
}

function calculateNewCanvasRect(zoomChange) {
    const canvasRect = zoomDiv.getBoundingClientRect();
    const newWidth = canvasRect.width*zoomChange;
    const newHeight = canvasRect.height*zoomChange;
    const xOffset = (newWidth - canvasRect.width) / 2;
    const yOffset = (newHeight - canvasRect.height) / 2;
    return new DOMRect(canvasRect.left - xOffset, canvasRect.top - yOffset, newWidth, newHeight);
}

function updatePlaceLabel() {
    const pos = getPlacePos();
    placePosLabel.innerHTML = "X: "+Math.round(pos[0])+", Y: "+Math.round(pos[1]);
}

function updatePlaceOutline() {
    if (currentZoomAmount >= 8 && placeOutline.hasAttribute("hidden")) {
        placeOutline.removeAttribute("hidden");
    } else if (currentZoomAmount < 8 && !placeOutline.hasAttribute("hidden")) {
        placeOutline.setAttribute("hidden", "");
    }

    const placePos = getPlacePos();
    const placeX = Math.round(placePos[0]);
    const placeY = Math.round(placePos[1]);
    if (!placeOutline.hasAttribute("hidden")) {
        const canvasRect = canvas.getBoundingClientRect();
        const x = canvasRect.left + placeX * currentZoomAmount - currentZoomAmount/8;
        const y = canvasRect.top + placeY * currentZoomAmount - currentZoomAmount/8;
        placeOutline.style.margin = ""+y+"px 0 0 "+x+"px";
        placeOutline.style.width = currentZoomAmount+"px";
        placeOutline.style.height = currentZoomAmount+"px";
        placeOutline.style.borderWidth = (currentZoomAmount/8)+"px";
    }
    const user = userList[placeX+placeY*canvasWidth];
    if (!(user === undefined)) {userLabel.innerHTML = "User: "+user;}
}

function startPlaceTimer(time, first = true) {
    if (!isAuthenticated) {return;}
    if (first) {
        onCooldown = true;
        placeButton.classList.add("place-button-cooldown");
    }
    const diff = (time - Date.now()) / 1000;
    if (diff > 0) {
        const minute = Math.floor(diff / 60);
        const seconds = Math.floor(diff % 60);
        placeLabel.innerHTML = ""+minute+":"+(seconds < 10 ? "0":"")+seconds;
        setTimeout(startPlaceTimer, 100, time, false);
    } else {
        onCooldown = false;
        placeButton.classList.remove("place-button-cooldown");
        placeLabel.innerHTML = "Place";
    }
}


// canvas moving

function getTranslation() {
	const style = window.getComputedStyle(moveDiv);
	const matrix = new WebKitCSSMatrix(style.transform);
    return [matrix.m41, matrix.m42];
}

function setTranslate(x, y) {
    moveDiv.style.transform = "translate("+x+"px, "+y+"px)";
    updatePlaceLabel();
    updatePlaceOutline();
}

function moveCanvas(moveX, moveY) {
    const pos = getTranslation();
    setTranslate(pos[0]+moveX, pos[1]+moveY);
}

function adjustForZoom(zoomChange) {
    const newRect = calculateNewCanvasRect(zoomChange);
    const pos = getPlacePos();
    const newPos = getPlacePos(newRect);
    moveCanvas((newPos[0]-pos[0])*currentZoomAmount, (newPos[1]-pos[1])*currentZoomAmount);
}

// canvas zooming

function setZoom(zoomElement, zoomAmount) {
    // adjust canvas position to keep the pixel position the same
    const zoomChange = zoomAmount / currentZoomAmount;
    currentZoomAmount = zoomAmount;
    adjustForZoom(zoomChange);

    // adjust zoom
    if (currentZoom != null) {
        currentZoom.classList.remove("picked-zoom-option");
    }
    zoomElement.classList.add("picked-zoom-option");
    zoomDiv.style.transform = "scale("+zoomAmount+", "+zoomAmount+")";
    currentZoom = zoomElement;

    // adjust target


    // update labels
    updatePlaceLabel();
    updatePlaceOutline();
}

// colors

function setColor(color) {
    currentlySelectedColor = color;
    placeOutline.style.backgroundColor = hexColors[color];
}

// events

onmousedown = (event) => {
    if (ws === null) {return;}
    for (const gui of guis) {
        const guiRect = gui.getBoundingClientRect();
        if (guiRect.left <= mousePos[0] && mousePos[0] <= guiRect.right &&
            guiRect.top <= mousePos[1] && mousePos[1] <= guiRect.bottom) {
            return;
        }
    }
    pressed = true;
};

onmouseup = (event) => {
    if (ws === null) {return;}
    pressed = false;
};

onmousemove = (event) => {
    if (ws === null) {return;}
    pressed = (event.buttons !== undefined ? event.buttons : event.which) & 1 === 1;
    mousePos[0] = event.clientX;
    mousePos[1] = event.clientY;
    if (pressed) {
        moveCanvas(event.movementX, event.movementY);
    }
};

onwheel = (event) => {
	scrollAmount += event.deltaY;
	if (scrollAmount <= -50) {
		scrollAmount = 0;
		if (currentZoomAmount < 32) {
			const zoom = currentZoomAmount * 2;
			setZoom(document.getElementById("zoom-"+zoom+"x"), zoom);
		}
	} else if (scrollAmount >= 50) {
		scrollAmount = 0;
		if (currentZoomAmount > 1) {
			const zoom = currentZoomAmount / 2;
			setZoom(document.getElementById("zoom-"+zoom+"x"), zoom);
		}
	}
};

const movementKeys = ["w", "a", "s", "d"];
const paintKeys = ["arrowup", "arrowleft", "arrowdown", "arrowright"];
onkeydown = (event) => {
    const key = event.key.toLowerCase();
    if (key == "enter") {
        onPlace();
    } else if (movementKeys.includes(key)) {
        const i = movementKeys.indexOf(key);
        const dir = (i & 2) ? -1:1;
        moveCanvas((i & 1)*dir*currentZoomAmount, (i & 1 ^ 1)*dir*currentZoomAmount);
    } else if (paintKeys.includes(key)) {
        const i = paintKeys.indexOf(key);
        const dir = (i & 2) ? 1:-1;
        setColor(Math.max(0, Math.min(colors.length, currentlySelectedColor + dir * ((i & 1) ? 1:4))));
    }
};

for (const zoomElement of zooms) {
    const match = zoomElement.id.match(/([0-9]+)x/);
    const zoomAmount = parseInt(match[1]);
    zoomElement.onclick = (event) => {
        if (ws === null) {return;}
        setZoom(zoomElement, zoomAmount);
    }
}

for (const colorOption of colorOptions) {
    const match = colorOption.id.match(/-([0-9]+)/);
    const color = parseInt(match[1]);
    colorOption.style.backgroundColor = hexColors[color];
    colorOption.onclick = (event) => {
        if (ws === null) {return;}
        setColor(color);
    }
}

function onPlace(event = null) {
    if (!isAuthenticated || currentZoomAmount < 8 || onCooldown) {return;}
    const pos = getPlacePos();
    ws.send("PLACE "+Math.round(pos[0])+" "+Math.round(pos[1])+" "+currentlySelectedColor);
}

if (placeButton) {
	placeButton.onclick = onPlace;
}


if (clearButton) {
    clearButton.onclick = (event) => {
        if (!isAuthenticated) {return;}
        const pos = getClearPos();
        if (pos[2]-pos[0] < 0 || pos[3]-pos[1] < 0) {return;}
        for (const value of [pos[0], pos[2]]) {
            if (!(0 <= value || value <= canvasWidth)) {return;}
        }
		for (const value of [pos[1], pos[3]]) {
            if (!(0 <= value || value <= canvasHeight)) {return;}
        }
        ws.send("CLEAR "+pos[0]+" "+pos[1]+" "+pos[2]+" "+pos[3]);
        resetClearPos();
    };
}

if (banButton) {
    banButton.onclick = (event) => {
        if (!isAuthenticated) {return;}
        const user = banInput.value;
        ws.send("BAN "+user);
        banInput.value = "";
    }
}

if (cooldownButton) {
    cooldownButton.onclick = (event) => {
        if (!isAuthenticated) {return;}
        const cooldown = cooldownInput.value;
        ws.send("SETCOOLDOWN "+cooldown);
        cooldownInput.value = "";
    }
}

// websocket

function checkIsAuthenticated() {
	return isAuthenticated;
}

function doWhenTrue(check, callback) {
	if (check()) {
		return callback();
	}
	setTimeout(doWhenTrue, 100, check, callback);
}

function popupError(message, timer = null) {
    errorLabel.innerHTML = message;
    if (errorBox.hasAttribute("hidden")) {
        errorBox.removeAttribute("hidden");
    }
    if (timer !== null) {
        setTimeout(() => {
            errorBox.setAttribute("hidden", "");
        }, timer);
    }
}

function pingServer() {
    if (ws !== null) {
        ws.send("PING");
        setTimeout(pingServer, 1000*60*5);
    }
}

function onOpen(event, authdata) {
    if (authdata.token) {
        ws.send("AUTH "+authdata.token);
    }
    pingServer();
}

function onMessage(event) {
    console.log(event.data);
    if (event.data.type === "") {
        event.data.arrayBuffer().then(data => {
            loadCanvas(data);
        });
    } else if (event.data.startsWith("PLACE")) {
        const match = event.data.match(/PLACE (\w*) ([0-9]+) ([0-9]+) ([0-9]+)/);
		const user = match[1];
		const x = parseInt(match[2]);
		const y = parseInt(match[3]);
		const color = parseInt(match[4]);
		doWhenTrue(checkIsAuthenticated, () => {placePixel(user, x, y, color);});
    } else if (event.data.startsWith("CLEAR")) {
        const match = event.data.match(/CLEAR ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+)/);
        clearCanvas(parseInt(match[1]), parseInt(match[2]), parseInt(match[3]), parseInt(match[4]));
    } else if (event.data.startsWith("USERS")) {
        userList = event.data.slice(6).split(' ');
        updatePlaceOutline();
    } else if (event.data.startsWith("COOLDOWN")) {
        const match = event.data.match(/COOLDOWN ([0-9]+)/);
		const cooldown = parseInt(match[1]);
		doWhenTrue(checkIsAuthenticated, () => {startPlaceTimer(cooldown);});
    } else if (event.data === "AUTHENTICATION SUCCESS") {
        isAuthenticated = true;
        setColor(0);
    } else if (event.data === "BANNED") {
        isAuthenticated = false;
        placeLabel.innerHTML = "Banned";
        placeButton.classList.add("place-button-cooldown");
        colorPicker.setAttribute("hidden", "");
        placeOutline.style.backgroundColor = "transparent";
        popupError("You have been banned. You can continue browsing but may no longer place.", 5000);
    }
}

function onClose(event) {
    console.log("Connection to webserver closed...");
    popupError("Websocket connection closed... try refreshing the website later.");
    ws = null;
    isAuthenticated = false;
}

function connect() {
    fetch("/token").then(response => {
        return response.json();
    }).then(authdata => {
        ws = new WebSocket("wss://bot.sheppsu.me/ws/");
        ws.binaryType = "blob";
        ws.onopen = (event) => {onOpen(event, authdata);};
        ws.onmessage = onMessage;
        ws.onerror = (event) => {console.log("Websocket error: ", event);}
        ws.onclose = onClose;
    });
}

// initialization

setZoom(document.getElementById("zoom-1x"), 1);
setTranslate(window.innerWidth/2-canvasWidth/2, window.innerHeight/2-canvasHeight/2);
connect();
