const ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
const CODE_LENGTH = 14;

const normalize = (code) => [...code.toUpperCase()].filter((c) => ALPHABET.includes(c)).join("");
const fromBase64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

async function decryptName(code, entry, iterations) {
  const material = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(code), "PBKDF2", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: fromBase64(entry.salt), iterations, hash: "SHA-256" },
    material, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: fromBase64(entry.iv) }, key, fromBase64(entry.ct));
  return new TextDecoder().decode(plain);
}

async function findName(rawCode, data) {
  const code = normalize(rawCode);
  const entry = code.length === CODE_LENGTH && data.entries[code.slice(0, 4)];
  if (!entry) return null;
  try {
    return await decryptName(code, entry, data.iterations);
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
    flake.textContent = "❄";
    flake.style.left = Math.random() * 100 + "vw";
    flake.style.fontSize = 0.6 + Math.random() * 1.2 + "rem";
    flake.style.animationDuration = 6 + Math.random() * 8 + "s";
    flake.style.animationDelay = -Math.random() * 14 + "s";
    $("snow").append(flake);
  }

  $("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("error").hidden = true;
    let name = null;
    try {
      const data = await (await fetch("data.json", { cache: "no-store" })).json();
      name = await findName(input.value, data);
    } catch {
      $("error").textContent = "No se pudo cargar el sorteo. Intenta de nuevo en un momento.";
      $("error").hidden = false;
      return;
    }
    if (!name) {
      $("error").textContent = "Código incorrecto. Revisa que esté completo.";
      $("error").hidden = false;
      return;
    }
    $("form").hidden = true;
    $("result").hidden = false;
    setTimeout(() => {
      $("gift").hidden = true;
      $("opening").hidden = true;
      $("name").textContent = name;
      $("reveal").hidden = false;
    }, 1600);
  });
}
