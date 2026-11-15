// reports.js
const panel = document.getElementById("reports-panel");
const title = document.getElementById("reports-title");
const list = document.getElementById("reports-list");

document.querySelectorAll(".see-reports").forEach(btn => {
    btn.addEventListener("click", async () => {
        title.textContent = "Reports for " + btn.dataset.name;
        list.textContent = "Loading...";
        panel.hidden = false;

        try {
            const res = await fetch(btn.dataset.url);
            if (!res.ok) throw new Error(res.status);
            const data = await res.json();

            list.textContent = "";
            if (data.length === 0) {
                list.textContent = "No reports yet.";
                return;
            }
            for (const r of data) {
                const li = document.createElement("li");
                const when = new Date(r.createdAt).toLocaleString();
                li.textContent = `${when}: ${r.status}` +
                    (r.minutesLeft ? ` (${r.minutesLeft} min left)` : "");
                list.appendChild(li);
            }
        } catch (e) {
            list.textContent = "Couldn't load reports.";
        }
    });
});