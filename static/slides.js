const slides = document.querySelectorAll(".slide");
  const dotsEl = document.getElementById("dots");
  const counter = document.getElementById("counter");
  const prog = document.getElementById("prog");
  let cur = 0;

  // Build dots
  slides.forEach((_, i) => {
    const d = document.createElement("div");
    d.className = "dot" + (i === 0 ? " on" : "");
    d.onclick = () => go(i);
    dotsEl.append(d);
  });

  function go(n) {
    slides[cur].classList.remove("active");
    dotsEl.children[cur].classList.remove("on");
    cur = (n + slides.length) % slides.length;
    slides[cur].classList.add("active");
    dotsEl.children[cur].classList.add("on");
    counter.textContent = (cur + 1) + " / " + slides.length;
    prog.style.width = ((cur + 1) / slides.length * 100) + "%";
  }

  document.getElementById("prev").onclick = () => go(cur - 1);
  document.getElementById("next").onclick = () => go(cur + 1);

  document.addEventListener("keydown", e => {
    if (e.key === "ArrowRight" || e.key === " ") go(cur + 1);
    if (e.key === "ArrowLeft") go(cur - 1);
  });

  // Touch swipe
  let tx = 0;
  document.addEventListener("touchstart", e => tx = e.touches[0].clientX);
  document.addEventListener("touchend", e => {
    const dx = e.changedTouches[0].clientX - tx;
    if (Math.abs(dx) > 50) go(cur + (dx < 0 ? 1 : -1));
  });

  // Init progress
  prog.style.width = (1 / slides.length * 100) + "%";
