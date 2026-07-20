/* Progressive enhancement: a copy button on every code block.

   The docs site is otherwise script-free; with JavaScript disabled every
   page works exactly the same, just without this one convenience. No
   frameworks, no external or third-party requests. Each <pre> is wrapped in
   a positioned .code-wrap so the button stays pinned to the block's corner
   while long lines scroll inside the <pre>. */
(function () {
  if (!navigator.clipboard || !document.querySelectorAll) return;

  var COPY =
    '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"' +
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="i-copy" aria-hidden="true">' +
    '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>';
  var DONE =
    '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"' +
    ' stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" class="i-done" aria-hidden="true">' +
    '<path d="M20 6L9 17l-5-5"/></svg>';

  document.querySelectorAll("pre").forEach(function (pre) {
    var wrap = document.createElement("div");
    wrap.className = "code-wrap";
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.setAttribute("aria-label", "Copy code");
    btn.innerHTML = COPY + DONE;
    btn.addEventListener("click", function () {
      var code = pre.querySelector("code") || pre;
      navigator.clipboard.writeText(code.textContent.replace(/\n+$/, "")).then(function () {
        btn.classList.add("copied");
        btn.setAttribute("aria-label", "Copied");
        clearTimeout(btn._t);
        btn._t = setTimeout(function () {
          btn.classList.remove("copied");
          btn.setAttribute("aria-label", "Copy code");
        }, 1500);
      });
    });
    wrap.appendChild(btn);
  });
})();
