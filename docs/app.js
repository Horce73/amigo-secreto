/**
 * AMIGO SECRETO - Cliente Seguro en el Navegador
 * Decodificación y descifrado local con Web Cryptography API (PBKDF2 + AES-GCM)
 */

const ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
const CODE_LENGTH = 14;

/**
 * Limpia y normaliza el código eliminando caracteres no válidos.
 */
function normalizeCode(raw) {
  if (!raw) return "";
  return [...raw.toUpperCase()].filter((c) => ALPHABET.includes(c)).join("");
}

/**
 * Formatea un código limpio con guiones: XXXX-XXXXX-XXXXX
 */
function formatCodeWithDashes(clean) {
  if (clean.length <= 4) return clean;
  if (clean.length <= 9) return `${clean.slice(0, 4)}-${clean.slice(4)}`;
  return `${clean.slice(0, 4)}-${clean.slice(4, 9)}-${clean.slice(9, 14)}`;
}

/**
 * Decodifica una cadena en base64 a Uint8Array.
 */
function fromBase64(text) {
  const binary = atob(text);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Descifra el contenido cifrado con AES-GCM usando la clave derivada del código.
 */
async function decryptPayload(code, entry, iterations) {
  const encoder = new TextEncoder();
  const rawKeyMaterial = encoder.encode(code);

  const baseKey = await crypto.subtle.importKey(
    "raw",
    rawKeyMaterial,
    "PBKDF2",
    false,
    ["deriveKey"]
  );

  const derivedKey = await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: fromBase64(entry.salt),
      iterations: iterations,
      hash: "SHA-256",
    },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );

  const decryptedBytes = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: fromBase64(entry.iv),
    },
    derivedKey,
    fromBase64(entry.ct)
  );

  const decoder = new TextDecoder("utf-8");
  return JSON.parse(decoder.decode(decryptedBytes));
}

/**
 * Busca y descifra la tarjeta correspondiente al código dado en el sorteo.
 */
async function resolveSecretFriend(rawCode, data) {
  const code = normalizeCode(rawCode);
  if (code.length !== CODE_LENGTH) {
    return null;
  }

  const prefix = code.slice(0, 4);
  const entry = data.entries && data.entries[prefix];
  if (!entry) {
    return null;
  }

  try {
    return await decryptPayload(code, entry, data.iterations);
  } catch (err) {
    return null;
  }
}

// ============================================================================
// Interfaz de Usuario e Interacciones
// ============================================================================
document.addEventListener("DOMContentLoaded", () => {
  const $ = (id) => document.getElementById(id);

  const form = $("reveal-form");
  const input = $("code");
  const errorBox = $("code-error");

  const formCard = $("form-card");
  const loadingCard = $("loading-card");
  const resultCard = $("result-card");
  const resultBadgeEl = $("result-badge");
  const resultTitle = $("result-title");
  const cluesProgressEl = $("clues-progress");
  const nameContainerEl = $("name-container");
  const revealedNameEl = $("revealed-name");
  const cluesSectionEl = $("clues-section");
  const cluesListEl = $("clues-list");
  const clueAnnouncerEl = $("clue-announcer");
  const secretDisclaimerEl = $("secret-disclaimer");
  const btnNextClue = $("btn-next-clue");
  const btnNextClueText = $("btn-next-clue-text");
  const btnReplayClues = $("btn-replay-clues");
  const btnReset = $("btn-reset");

  let currentPayload = null;
  let currentClues = [];
  let revealedClueCount = 0;

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --------------------------------------------------------------------------
  // Nieve navideña sutil en segundo plano (suave y pacífica)
  // --------------------------------------------------------------------------
  const starsCanvas = $("stars-canvas");
  if (starsCanvas && !prefersReducedMotion) {
    const ctx = starsCanvas.getContext("2d");
    let flakes = [];
    let width = 0;
    let height = 0;
    let animId = null;

    function resizeSnow() {
      width = window.innerWidth;
      height = window.innerHeight;
      starsCanvas.width = width;
      starsCanvas.height = height;

      flakes = Array.from({ length: 48 }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        radius: Math.random() * 1.8 + 0.6,
        alpha: Math.random() * 0.6 + 0.25,
        speedY: Math.random() * 0.7 + 0.35,
        swaySpeed: Math.random() * 0.02 + 0.008,
        swayAngle: Math.random() * Math.PI * 2,
        swayDistance: Math.random() * 0.5 + 0.2,
      }));
    }

    function drawSnow() {
      ctx.clearRect(0, 0, width, height);
      for (const f of flakes) {
        f.y += f.speedY;
        f.swayAngle += f.swaySpeed;
        f.x += Math.sin(f.swayAngle) * f.swayDistance;

        if (f.y > height) {
          f.y = -5;
          f.x = Math.random() * width;
        }
        if (f.x > width) f.x = 0;
        if (f.x < 0) f.x = width;

        ctx.beginPath();
        ctx.arc(f.x, f.y, f.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(247, 243, 238, ${f.alpha})`;
        ctx.fill();
      }
      animId = requestAnimationFrame(drawSnow);
    }

    window.addEventListener("resize", resizeSnow, { passive: true });
    resizeSnow();
    drawSnow();

    document.addEventListener("visibilitychange", () => {
      if (document.hidden && animId) {
        cancelAnimationFrame(animId);
      } else if (!document.hidden) {
        drawSnow();
      }
    });
  }

  // --------------------------------------------------------------------------
  // Confetti / Celebración artesanal al revelar
  // --------------------------------------------------------------------------
  const confettiCanvas = $("confetti-canvas");
  function launchCelebration() {
    if (prefersReducedMotion || !confettiCanvas) return;

    const ctx = confettiCanvas.getContext("2d");
    const width = (confettiCanvas.width = window.innerWidth);
    const height = (confettiCanvas.height = window.innerHeight);

    // Paleta oficial: Mulled Wine, Holly Leaf, Eggnog Cream, Cinnamon Sugar, Frosty Silver
    const colors = ["#78211E", "#616852", "#D8C8B8", "#BB9771", "#BEB3AC"];
    const particles = [];
    const particleCount = 55;

    for (let i = 0; i < particleCount; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Math.random() * 9 + 4;
      particles.push({
        x: width / 2,
        y: height / 2 - 50,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 3,
        size: Math.random() * 6 + 3,
        color: colors[Math.floor(Math.random() * colors.length)],
        rotation: Math.random() * 360,
        rotSpeed: (Math.random() - 0.5) * 12,
        opacity: 1,
        drag: 0.96,
        gravity: 0.22,
      });
    }

    let frame = 0;
    function renderConfetti() {
      ctx.clearRect(0, 0, width, height);
      let alive = false;

      for (const p of particles) {
        p.vx *= p.drag;
        p.vy *= p.drag;
        p.vy += p.gravity;
        p.x += p.vx;
        p.y += p.vy;
        p.rotation += p.rotSpeed;
        p.opacity -= 0.012;

        if (p.opacity > 0) {
          alive = true;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate((p.rotation * Math.PI) / 180);
          ctx.globalAlpha = Math.max(0, p.opacity);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
          ctx.restore();
        }
      }

      frame++;
      if (alive && frame < 180) {
        requestAnimationFrame(renderConfetti);
      } else {
        ctx.clearRect(0, 0, width, height);
      }
    }

    renderConfetti();
  }

  // --------------------------------------------------------------------------
  // Auto-formateo del input mientras se escribe
  // --------------------------------------------------------------------------
  input.addEventListener("input", (e) => {
    hideError();
    const clean = normalizeCode(e.target.value);
    const formatted = formatCodeWithDashes(clean);
    if (e.target.value !== formatted) {
      e.target.value = formatted;
    }
  });

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.hidden = false;
  }

  function hideError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function setLoading(loading) {
    if (loading) {
      formCard.hidden = true;
      resultCard.hidden = true;
      loadingCard.hidden = false;
    } else {
      loadingCard.hidden = true;
    }
  }

  function sanitizeImageUrl(rawUrl) {
    if (typeof rawUrl !== "string") return "";
    const trimmed = rawUrl.trim();
    if (!trimmed || /[\u0000-\u001f\u007f]/.test(trimmed)) return "";
    // Evitar traversal en rutas locales
    if (trimmed.split(/[\\/]/).includes("..")) return "";

    try {
      const parsed = new URL(trimmed, window.location.href);
      if (parsed.protocol === "https:" || parsed.protocol === "http:") {
        return trimmed;
      }
    } catch {
      return "";
    }
    return "";
  }

  function normalizeClues(rawClues) {
    if (!Array.isArray(rawClues)) return [];
    return rawClues
      .map((rawClue) => {
        if (typeof rawClue === "string") {
          const text = rawClue.trim();
          return text ? { text, image: "" } : null;
        }
        if (Array.isArray(rawClue)) {
          const text = rawClue.map((part) => String(part ?? "").trim()).filter(Boolean).join(": ");
          return text ? { text, image: "" } : null;
        }
        if (rawClue && typeof rawClue === "object") {
          const text = String(rawClue.text ?? "").trim();
          const image = sanitizeImageUrl(rawClue.image);
          return text || image ? { text, image } : null;
        }
        return null;
      })
      .filter(Boolean);
  }

  function appendClueItem(clue) {
    const li = document.createElement("li");
    li.className = "clue-item";

    const bullet = document.createElement("span");
    bullet.className = "clue-bullet";
    bullet.setAttribute("aria-hidden", "true");
    bullet.textContent = "✦";

    const body = document.createElement("div");
    body.className = "clue-body";

    if (clue.text) {
      const label = document.createElement("span");
      label.className = "clue-text";
      label.textContent = clue.text;
      body.append(label);
    }

    if (clue.image) {
      const media = document.createElement("div");
      media.className = "clue-media";

      const img = document.createElement("img");
      img.className = "clue-image";
      img.src = clue.image;
      img.alt = clue.text ? `Imagen de la característica: ${clue.text}` : "Imagen de pista del amigo secreto";
      img.decoding = "async";
      img.loading = "eager";
      img.addEventListener("error", () => {
        media.remove();
        if (!clue.text) {
          li.remove();
        }
      }, { once: true });

      media.append(img);
      body.append(media);
    }

    li.append(bullet, body);
    cluesListEl.append(li);
  }

  function updateClueControls() {
    const total = currentClues.length;
    cluesProgressEl.textContent = `Característica ${revealedClueCount} de ${total}`;
    const hasMore = revealedClueCount < total;
    btnNextClueText.textContent = hasMore ? "Siguiente característica" : "Revelar quién es";
  }

  function advanceClue(announce) {
    if (revealedClueCount >= currentClues.length) return;
    const clue = currentClues[revealedClueCount];
    revealedClueCount += 1;
    appendClueItem(clue);
    updateClueControls();

    if (announce) {
      const spoken = clue.text || "Imagen de pista";
      clueAnnouncerEl.textContent = `Característica ${revealedClueCount} de ${currentClues.length}: ${spoken}`;
    }
  }

  function revealFinalName() {
    if (!currentPayload) return;
    resultBadgeEl.textContent = "Asignación Confidencial";
    resultTitle.textContent = "Te tocó regalarle a:";
    cluesProgressEl.hidden = true;
    btnNextClue.hidden = true;
    nameContainerEl.hidden = false;
    secretDisclaimerEl.hidden = false;
    btnReplayClues.hidden = currentClues.length === 0;
    clueAnnouncerEl.textContent = `Tu amigo secreto es ${currentPayload.name}.`;

    launchCelebration();
    resultTitle.focus();
  }

  function startCluesStepFlow() {
    cluesListEl.replaceChildren();
    revealedClueCount = 0;
    nameContainerEl.hidden = true;
    secretDisclaimerEl.hidden = true;
    btnReplayClues.hidden = true;
    cluesSectionEl.hidden = false;
    resultBadgeEl.textContent = "Pistas Confidenciales";
    resultTitle.textContent = "¿Quién será tu amigo secreto?";
    cluesProgressEl.hidden = false;
    btnNextClue.hidden = false;

    advanceClue(false);
    btnNextClue.focus();
  }

  // --------------------------------------------------------------------------
  // Flujo de revelación
  // --------------------------------------------------------------------------
  async function performReveal(rawCode) {
    hideError();
    const clean = normalizeCode(rawCode);

    if (clean.length !== CODE_LENGTH) {
      showError("El código debe tener 14 caracteres. Revisa que esté completo.");
      input.focus();
      return;
    }

    setLoading(true);

    let data = null;
    try {
      const response = await fetch("data.json", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("No se pudo leer data.json");
      }
      data = await response.json();
    } catch (err) {
      setLoading(false);
      formCard.hidden = false;
      showError("No se pudo cargar el sorteo. Intenta recargar la página.");
      return;
    }

    const payload = await resolveSecretFriend(clean, data);

    if (!payload || !payload.name) {
      setLoading(false);
      formCard.hidden = false;
      showError("Código no válido o no encontrado en el sorteo.");
      input.focus();
      return;
    }

    // Éxito: Mostrar características paso a paso antes de revelar el nombre
    setLoading(false);
    currentPayload = payload;
    currentClues = normalizeClues(payload.clues);
    revealedNameEl.textContent = payload.name;
    formCard.hidden = true;
    resultCard.hidden = false;

    if (currentClues.length > 0) {
      startCluesStepFlow();
    } else {
      cluesSectionEl.hidden = true;
      cluesListEl.replaceChildren();
      revealFinalName();
    }
  }

  // --------------------------------------------------------------------------
  // Controles de pistas y reinicio
  // --------------------------------------------------------------------------
  btnNextClue.addEventListener("click", () => {
    if (revealedClueCount < currentClues.length) {
      advanceClue(true);
    } else {
      revealFinalName();
    }
  });

  btnReplayClues.addEventListener("click", () => {
    if (currentClues.length > 0) {
      startCluesStepFlow();
    }
  });

  // --------------------------------------------------------------------------
  // Envío del formulario
  // --------------------------------------------------------------------------
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    performReveal(input.value);
  });

  // --------------------------------------------------------------------------
  // Reiniciar formulario para ingresar otro código
  // --------------------------------------------------------------------------
  btnReset.addEventListener("click", () => {
    resultCard.hidden = true;
    nameContainerEl.hidden = true;
    cluesSectionEl.hidden = true;
    cluesProgressEl.hidden = true;
    btnNextClue.hidden = true;
    btnReplayClues.hidden = true;
    secretDisclaimerEl.hidden = true;
    cluesListEl.replaceChildren();
    clueAnnouncerEl.textContent = "";
    currentPayload = null;
    currentClues = [];
    revealedClueCount = 0;
    formCard.hidden = false;
    input.value = "";
    hideError();
    input.focus();
  });

  // --------------------------------------------------------------------------
  // Detección automática de código en URL Hash (#XXXX-XXXXX-XXXXX)
  // --------------------------------------------------------------------------
  const initialHash = window.location.hash ? window.location.hash.slice(1) : "";
  if (initialHash) {
    const cleanHash = normalizeCode(initialHash);
    if (cleanHash) {
      input.value = formatCodeWithDashes(cleanHash);
      // Limpiar hash de la URL para confidencialidad
      history.replaceState(null, "", window.location.pathname + window.location.search);
      performReveal(cleanHash);
    }
  }
});
