// Top navigation, enhanced: the phone menu button and the Cities menu's type-to-filter. Without
// this file the nav is a wrapping row of links and the Cities menu a plain <details> list.

const root = document.documentElement;
root.classList.add("js");

const header = document.querySelector("header.site");
const toggle = header?.querySelector(".menu-toggle");
if (header && toggle) {
  toggle.hidden = false;
  toggle.addEventListener("click", () => {
    const open = header.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
  });
}

const menu = document.querySelector("details.cities-menu");
const filter = menu?.querySelector(".city-filter");
if (menu && filter) {
  filter.hidden = false;
  const groups = [...menu.querySelectorAll(".grp")];
  const none = menu.querySelector(".no-match");
  const apply = () => {
    const q = filter.value.trim().toLowerCase();
    let shown = 0;
    for (const g of groups) {
      const countryHit = g.dataset.country.toLowerCase().includes(q);
      let any = false;
      for (const li of g.querySelectorAll("li")) {
        const hit = !q || countryHit || li.textContent.toLowerCase().includes(q);
        li.hidden = !hit;
        any ||= hit;
      }
      g.hidden = !any;
      if (any) shown += 1;
    }
    if (none) none.hidden = shown > 0;
  };
  filter.addEventListener("input", apply);
  filter.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const first = menu.querySelector(".grp:not([hidden]) li:not([hidden]) a");
      if (first) location.href = first.getAttribute("href");
    }
  });
  menu.addEventListener("toggle", () => {
    if (!menu.open) return;
    filter.value = "";
    apply();
    if (matchMedia("(hover: hover)").matches) filter.focus();
  });
  document.addEventListener("click", (e) => {
    if (menu.open && !menu.contains(e.target)) menu.open = false;
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && menu.open) {
      menu.open = false;
      menu.querySelector("summary").focus();
    }
  });
}
