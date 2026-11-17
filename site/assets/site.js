document.addEventListener("DOMContentLoaded", () => {
  const narrow = matchMedia("(max-width: 760px)");
  const reference = document.querySelector(".nav-shared");
  if (reference) {
    const adaptNavigation = () => { reference.open = !narrow.matches; };
    adaptNavigation();
    narrow.addEventListener("change", adaptNavigation);
  }

  for (const block of document.querySelectorAll(".code-block")) {
    const code = block.querySelector("code");
    const toolbar = block.querySelector(".code-toolbar");
    if (!code || !toolbar || !navigator.clipboard) continue;
    const status = document.createElement("span");
    status.className = "copy-status";
    status.setAttribute("role", "status");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = "Copy";
    button.setAttribute("aria-label", "Copy code");
    let reset;
    button.addEventListener("click", async () => {
      clearTimeout(reset);
      button.disabled = true;
      try {
        await navigator.clipboard.writeText(code.textContent);
        status.textContent = "Copied";
      } catch {
        status.textContent = "Copy failed. Select and copy the code.";
      } finally {
        button.disabled = false;
      }
      reset = setTimeout(() => { status.textContent = ""; }, 4000);
    });
    toolbar.append(status, button);
  }

  const scrollRegions = document.querySelectorAll(".table-wrap, .code-block pre, pre.mermaid");
  const scrollHints = new Map();
  for (const region of scrollRegions) {
    if (!region.matches(".table-wrap, .mermaid")) continue;
    const hint = document.createElement("p");
    hint.className = "scroll-hint";
    hint.hidden = true;
    hint.textContent = region.classList.contains("table-wrap")
      ? "Scroll to see all columns \u2192"
      : "Scroll to see the full diagram \u2192";
    region.before(hint);
    scrollHints.set(region, hint);
  }
  const labelScrollRegions = () => {
    for (const region of scrollRegions) {
      const scrollable = region.scrollWidth > region.clientWidth + 1;
      const hint = scrollHints.get(region);
      if (hint) hint.hidden = !scrollable;
      if (scrollable) {
        region.tabIndex = 0;
        region.setAttribute("role", "region");
        const type = region.classList.contains("table-wrap") ? "Table" : region.classList.contains("mermaid") ? "Diagram" : "Code";
        region.setAttribute("aria-label", `${type}; scroll horizontally to see all content`);
      } else {
        region.removeAttribute("tabindex");
        region.removeAttribute("role");
        region.removeAttribute("aria-label");
      }
    }
  };
  labelScrollRegions();
  if ("ResizeObserver" in window) {
    const resize = new ResizeObserver(labelScrollRegions);
    for (const region of scrollRegions) resize.observe(region);
  }

  const links = new Map();
  for (const link of document.querySelectorAll(".toc a[href^='#']")) {
    const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
    if (target) links.set(target, link);
  }
  if (!links.size || !("IntersectionObserver" in window)) return;
  const markCurrent = (target) => {
    for (const [heading, link] of links) {
      link.classList.toggle("active", heading === target);
      if (heading === target) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  };
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) markCurrent(entry.target);
    }
  }, { rootMargin: "-40px 0px -65% 0px" });
  for (const heading of links.keys()) observer.observe(heading);
});
