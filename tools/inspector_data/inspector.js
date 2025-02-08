// Bridge with Python for retrieving images
let python;
new QWebChannel(qt.webChannelTransport, function(channel) {
    python = channel.objects.python;
});

window.onload = function() {
    // Wait for QWebChannel to be ready
    if (typeof python === "undefined") {
        setTimeout(window.onload, 100);
        return;
    }

    // Render each element roughly based on the UI script.
    // Many attributes origin from older Maxis games and may not be used.
    document.querySelectorAll(".LEGACY").forEach((element) => {
        const clsid = element.getAttribute("clsid");
        const iid = element.getAttribute("iid");

        // Parse UI script attributes
        const _area = element.getAttribute("area") ? element.getAttribute("area").slice(1, -1).split(',') : [0,0,0,0]; // (startX, startY, endX, endY)
        const area = {
            x: parseInt(_area[0]),
            y: parseInt(_area[1]),
            width: parseInt(_area[2]) - parseInt(_area[0]),
            height: parseInt(_area[3]) - parseInt(_area[1]),
        };

        const _gutters = element.getAttribute("gutters") ? element.getAttribute("gutters") : [0,0,0,0]; // (left, top, right, bottom) or (left/right, top/bottom)
        const gutters = {
            left: parseInt(_gutters[0]),
            top: parseInt(_gutters[1]),
            right: parseInt(_gutters[2]),
            bottom: parseInt(_gutters[3]),
        };

        const _fillcolor = `rgb${element.getAttribute("fillcolor")}`;
        const _bkgcolor = `rgb${element.getAttribute("bkgcolor")}`;
        const background = element.getAttribute("fillcolor") ? _fillcolor : _bkgcolor;
        const forecolor = `rgb${element.getAttribute("forecolor")}`;

        const image = element.getAttribute("image");
        const caption = element.getAttribute("caption");
        const noShowCaption = element.getAttribute("showcaption") == "no";
        const tips = element.getAttribute("tips") === "yes" || false;
        const align = element.getAttribute("align") || "left"; // left, right, center, lefttop

        // Transform into HTML layout
        element.classList.add(element.getAttribute("clsid"));

        /* Area */
        element.style.position = "absolute";
        element.style.top = `${area.y}px`;
        element.style.left = `${area.x}px`;
        element.style.height = `${area.height}px`;
        element.style.width = `${area.width}px`;

        /* Gutters */
        element.style.paddingTop = `${gutters.top}px`;
        element.style.paddingRight = `${gutters.right}px`;
        element.style.paddingBottom = `${gutters.bottom}px`;
        element.style.paddingLeft = `${gutters.left}px`;

        /* Colours */
        element.style.color = forecolor;
        if (iid === "IGZWinCustom")
            element.style.backgroundColor = background;

        /* Load images */
        if (image) {
            python.get_image(image, function(b64data) {
                if (!b64data && element.children.length === 0) {
                    element.style.backgroundColor = "red";
                    element.classList.add("missing");
                    return;
                }
                const style = document.createElement("style");
                style.innerHTML = `.${clsid}[image="${image}"] { background-image: url(data:image/png;base64,${b64data}); }`;
                document.body.appendChild(style);
            });
        }

        /* Show text unless it seems likely to be a image button or contains technical key/value data */
        if (caption && !noShowCaption && !tips && caption.search("=") === -1) {
            element.innerText = element.getAttribute("caption");
        }

        if (tips)
            element.setAttribute("title", element.getAttribute("tiptext"));
    });

    // CHILDREN should be nested into the previous LEGACY element
    while (document.querySelectorAll(".CHILDREN").length > 0) {
        let childElement = document.querySelector(".CHILDREN");
        let parent = childElement.previousElementSibling;
        while (childElement.children.length > 0) {
            parent.appendChild(childElement.children[0]);
        }
        childElement.remove();
    };
};
