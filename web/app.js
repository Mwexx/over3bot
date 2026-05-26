const clock = document.querySelector("#clock");

function tick() {
  const now = new Date();
  const stamp = now.toISOString().slice(0, 19).replace("T", " ");
  clock.textContent = `${stamp} GMT`;
}

tick();
setInterval(tick, 1000);
