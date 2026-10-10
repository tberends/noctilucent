const toggle = document.querySelector(".menu-toggle");
const nav = document.querySelector("#site-nav");

if (toggle && nav) {
    toggle.addEventListener("click", () => {
        const open = nav.getAttribute("data-open") !== "true";
        nav.setAttribute("data-open", open ? "true" : "false");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    nav.addEventListener("click", (event) => {
        if (event.target.closest("a")) {
            nav.setAttribute("data-open", "false");
            toggle.setAttribute("aria-expanded", "false");
        }
    });
}
