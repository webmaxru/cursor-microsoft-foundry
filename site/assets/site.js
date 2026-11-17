// Copy buttons for code blocks and current-section highlighting in the page outline.
document.addEventListener("DOMContentLoaded", () => {
  for (const pre of document.querySelectorAll("pre:not(.mermaid)")) {
    const code = pre.querySelector("code");
    if (!code || !navigator.clipboard) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = "Copy";
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(code.innerText);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Copy failed";
      }
      setTimeout(() => { button.textContent = "Copy"; }, 1500);
    });
    pre.append(button);
  }

  const links = new Map();
  for (const link of document.querySelectorAll(".toc a[href^='#']")) {
    const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
    if (target) links.set(target, link);
  }
  if (!links.size || !("IntersectionObserver" in window)) return;
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      for (const link of links.values()) link.classList.remove("active");
      links.get(entry.target).classList.add("active");
    }
  }, { rootMargin: "-80px 0px -70% 0px" });
  for (const heading of links.keys()) observer.observe(heading);
});
