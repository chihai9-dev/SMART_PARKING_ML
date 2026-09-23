document.addEventListener("DOMContentLoaded", () => {
    const tbody = document.querySelector("#openTable tbody");
    if (!tbody) return;

    fetch("/api/tickets?status=open")
        .then((r) => r.json())
        .then((data) => {
            tbody.innerHTML = "";
            (data.tickets || []).forEach((t) => {
                const tr = document.createElement("tr");
                tr.innerHTML = `<td><strong>${t.ticket_code || ("#" + t.id)}</strong></td>
                    <td>${t.plate || ""}</td><td>${t.vehicle_type || ""}</td>
                    <td>${t.entry_time || ""}</td><td>${t.predicted_behavior || ""}</td>
                    <td>${t.recommended_zone || ""}</td><td>${t.estimated_exit || ""}</td><td>Đang gửi</td>`;
                tbody.appendChild(tr);
            });
        })
        .catch(() => {
            tbody.innerHTML = "<tr><td colspan='8'>Không tải được danh sách vé.</td></tr>";
        });
});
