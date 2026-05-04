\
(() => {
  const el = document.getElementById("examples-data");
  const grid = document.getElementById("examples-grid");
  if (!el || !grid) return;

  const categories = JSON.parse(el.textContent || "[]");

  function makeCard(cat) {
    const a = document.createElement("a");
    a.className = "examples-card";
    // page is relative to /examples/ (because we are on examples/index.html)
    a.href = cat.page || "#";

    const img = document.createElement("img");
    img.className = "examples-card__img";
    img.alt = cat.title || "Example";
    img.loading = "lazy";

    const overlay = document.createElement("div");
    overlay.className = "examples-card__overlay";

    const h = document.createElement("div");
    h.className = "examples-card__title";
    h.textContent = cat.title || "";

    overlay.appendChild(h);

    const imgs = Array.isArray(cat.images) ? cat.images : [];
    let i = 0;
    img.src = imgs[0] || "_static/no_image.png";

    let timer = null;
    a.addEventListener("mouseenter", () => {
      if (imgs.length <= 1) return;
      timer = window.setInterval(() => {
        i = (i + 1) % imgs.length;
        img.src = imgs[i];
      }, 900);
    });
    a.addEventListener("mouseleave", () => {
      if (timer) window.clearInterval(timer);
      timer = null;
      i = 0;
      img.src = imgs[0] || "_static/no_image.png";
    });

    a.appendChild(img);
    a.appendChild(overlay);
    return a;
  }

  categories.forEach(cat => grid.appendChild(makeCard(cat)));
})();
