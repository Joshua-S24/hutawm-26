// geolocation.js
function askLocation(url) {
    const status = document.getElementById("geo_status");
    if (!navigator.geolocation) {
        status.textContent = "Geolocation is not supported by your browser.";
        return;
    }
    status.textContent = "Requesting location...";

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            try {
                const res = await fetch(url, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                    }),
                });
                const data = await res.json();
                if (data.verified) status.textContent = "Location verified.";
                else if (data.reason === "unavailable")
                    status.textContent = "This room does not have a public location.";
                else status.textContent = "You don't appear to be at this room.";
            } catch (e) {
                status.textContent = "Couldn't verify location.";
            }
        },
        () => { status.textContent = "Permission denied or location unavailable."; },
        { enableHighAccuracy: true, timeout: 10000 }
    );
}