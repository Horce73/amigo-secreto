const ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
const CODE_LENGTH = 14;

const normalize = (code) => [...code.toUpperCase()].filter((c) => ALPHABET.includes(c)).join("");
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const fromBase64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

async function decryptPayload(code, entry, iterations) {
  const material = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(code), "PBKDF2", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: fromBase64(entry.salt), iterations, hash: "SHA-256" },
    material, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: fromBase64(entry.iv) }, key, fromBase64(entry.ct));
  return JSON.parse(new TextDecoder().decode(plain));
}

async function findCard(rawCode, data) {
  const code = normalize(rawCode);
  const entry = code.length === CODE_LENGTH && data.entries[code.slice(0, 4)];
  if (!entry) return null;
  try {
    return await decryptPayload(code, entry, data.iterations);
  } catch {
    return null;
  }
}

if (typeof document !== "undefined") {
  const $ = (id) => document.getElementById(id);
  const input = $("code");

  input.value = location.hash.slice(1);
  history.replaceState(null, "", location.pathname + location.search);

  for (let i = 0; i < 35; i++) {
    const flake = document.createElement("span");
    flake.textContent = "✦";
    flake.style.left = Math.random() * 100 + "vw";
    flake.style.fontSize = 0.6 + Math.random() * 1.2 + "rem";
    flake.style.animationDuration = 6 + Math.random() * 8 + "s";
    flake.style.animationDelay = -Math.random() * 14 + "s";
    $("snow").append(flake);
  }

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const wait = (ms) => (reduceMotion ? Promise.resolve() : sleep(ms));
  let run = 0;

  function burst() {
    if (reduceMotion) return;
    for (let i = 0; i < 28; i++) {
      const piece = document.createElement("span");
      piece.textContent = ["⭐", "🎉", "✨", "💫"][i % 4];
      const angle = Math.random() * Math.PI * 2;
      const distance = 120 + Math.random() * 220;
      piece.style.setProperty("--dx", Math.cos(angle) * distance + "px");
      piece.style.setProperty("--dy", Math.sin(angle) * distance + "px");
      $("burst").append(piece);
      setTimeout(() => piece.remove(), 1500);
    }
  }

  async function play(card) {
    const mine = ++run;
    $("replay").hidden = true;
    $("card").hidden = true;
    $("card").classList.remove("flipped");
    $("clues").replaceChildren();
    $("gift").hidden = false;
    $("opening").hidden = false;
    await wait(1600);
    if (mine !== run) return;

    $("gift").hidden = true;
    $("opening").hidden = true;
    $("name").textContent = card.name;
    $("card").hidden = false;
    await wait(700);

    for (const [label, value] of card.clues) {
      if (mine !== run) return;
      const row = document.createElement("li");
      const left = document.createElement("span");
      const right = document.createElement("span");
      left.className = "label";
      right.className = "value";
      left.textContent = label;
      right.textContent = value;
      row.append(left, right);
      $("clues").append(row);
      await wait(1300);
    }
    if (mine !== run) return;

    await wait(900);
    $("card").classList.add("flipped");
    await wait(700);
    burst();
    $("replay").hidden = false;
  }

  $("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("error").hidden = true;
    let card = null;
    try {
      const data = await (await fetch("data.json", { cache: "no-store" })).json();
      card = await findCard(input.value, data);
    } catch {
      $("error").textContent = "No se pudo cargar el sorteo. Intenta de nuevo en un momento.";
      $("error").hidden = false;
      return;
    }
    if (!card) {
      $("error").textContent = "Código incorrecto. Revisa que esté completo.";
      $("error").hidden = false;
      return;
    }
    $("form").hidden = true;
    $("result").hidden = false;
    $("replay").onclick = () => play(card);
    play(card);
  });
}
