/**
 * Cat walk animation for demo-login page
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

(function() {
	const state = {
		posX: 0,
		posY: 0,
		facing: 1, // 1: right, -1: left
		orbiting: false,
		orbitFrame: 0,
		gaitTime: 0,
		spawned: false,
		emerged: false,
		exited: false,
		rafId: null
	};

	function createCatElement() {
		const cat = document.createElement('div');
		cat.id = 'mg-cat';
		cat.setAttribute('aria-hidden', 'true');
		cat.style.position = 'fixed';
		cat.style.left = '0px';
		cat.style.top = '0px';
		cat.style.width = '110px';
		cat.style.height = '78px';
		cat.style.zIndex = '3';
		cat.style.pointerEvents = 'none';
		cat.style.filter = 'drop-shadow(0 6px 6px rgba(0,0,0,0.25))';
		cat.style.transform = 'translate(-9999px, -9999px)';

		cat.innerHTML =
			'<svg viewBox="0 0 200 140" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">\
				<defs>\
					<style>\
						#tail, #earL, #earR, #legFL, #legFR, #legBL, #legBR, #eyes, #head { transform-box: fill-box; transform-origin: center; }\
						#tail { transform-origin: 90% 50%; }\
						#legFL, #legFR, #legBL, #legBR { transform-origin: 50% 10%; }\
					</style>\
				</defs>\
				<g id="cat" fill="#0b0b0f">\
					<!-- body -->\
					<ellipse cx="120" cy="85" rx="58" ry="34"></ellipse>\
					<!-- head group -->\
					<g id="head">\
						<circle cx="65" cy="70" r="26"></circle>\
						<!-- ears -->\
						<polygon id="earL" points="52,56 42,34 64,45" />\
						<polygon id="earR" points="78,56 96,34 72,45" />\
						<!-- eyes -->\
						<g id="eyes">\
							<ellipse id="eyeL" cx="60" cy="70" rx="4" ry="4" fill="#f5f5f5"/>\
							<ellipse id="eyeR" cx="72" cy="70" rx="4" ry="4" fill="#f5f5f5"/>\
						</g>\
					</g>\
					<!-- tail -->\
					<rect id="tail" x="168" y="60" width="14" height="56" rx="8"/>\
					<path id="tailArc" d="M182 70 Q198 82 190 100" stroke="#0b0b0f" stroke-width="10" fill="none" stroke-linecap="round"/>\
				</g>\
				<!-- legs on top for clear overlap -->\
				<g id="legs" fill="#0b0b0f">\
					<rect id="legFL" x="88" y="100" width="12" height="28" rx="5"/>\
					<rect id="legFR" x="112" y="100" width="12" height="28" rx="5"/>\
					<rect id="legBL" x="136" y="100" width="12" height="28" rx="5"/>\
					<rect id="legBR" x="160" y="100" width="12" height="28" rx="5"/>\
				</g>\
			</svg>';

		return cat;
	}

	function placeCat(cat, x, y, facing) {
		state.posX = x;
		state.posY = y;
		if (typeof facing === 'number') state.facing = facing;
		cat.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px) scaleX(${-state.facing})`;
	}

	function getButtonSpawnPoint() {
		const btn = document.getElementById('submitBtn');
		if (!btn) return { x: 24, y: window.innerHeight - 120 };
		const r = btn.getBoundingClientRect();
		return { x: r.left + r.width * 0.5, y: r.top + r.height * 0.5 };
	}

	function getButtonOrbitCenter() {
		const btn = document.getElementById('submitBtn');
		if (!btn) return { x: window.innerWidth * 0.5, y: window.innerHeight * 0.7 };
		const r = btn.getBoundingClientRect();
		return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
	}

	function getPanelTrackRect(marginPx) {
		const panel = document.querySelector('.demo-container');
		const el = panel || document.getElementById('submitBtn');
		if (!el) return { left: 200, top: 200, width: 300, height: 200 };
		const r = el.getBoundingClientRect();
		return {
			left: r.left - marginPx,
			top: r.top - marginPx,
			width: r.width + 2 * marginPx,
			height: r.height + 2 * marginPx
		};
	}

	function getApproachPoint() {
		const btn = document.getElementById('submitBtn');
		if (!btn) return { x: 240, y: window.innerHeight - 120 };
		const r = btn.getBoundingClientRect();
		return { x: r.left + r.width * 0.15, y: r.top + r.height + 8 };
	}

	function animateBlink(cat) {
		const eyes = cat.querySelector('#eyes');
		if (!eyes) return;
		function blink() {
			if (state.exited) return;
			eyes.animate([
				{ transform: 'scaleY(1)' },
				{ transform: 'scaleY(0.1)' },
				{ transform: 'scaleY(1)' }
			], { duration: 110, easing: 'ease-in-out' });
			setTimeout(blink, 1200 + Math.random() * 2500);
		}
		setTimeout(blink, 800 + Math.random() * 1200);
	}

	function animateTail(cat) {
		const tail = cat.querySelector('#tail');
		if (!tail) return;
		tail.animate([
			{ transform: 'rotate(6deg)' },
			{ transform: 'rotate(-8deg)' },
			{ transform: 'rotate(6deg)' }
		], { duration: 1600, iterations: Infinity, easing: 'ease-in-out' });
	}

	function animateEars(cat) {
		const earL = cat.querySelector('#earL');
		const earR = cat.querySelector('#earR');
		if (!earL || !earR) return;
		function flick(ear, sign) {
			if (state.exited) return;
			ear.animate([
				{ transform: 'rotate(0deg)' },
				{ transform: `rotate(${sign * 10}deg)` },
				{ transform: 'rotate(0deg)' }
			], { duration: 260, easing: 'ease-out' });
		}
		setInterval(() => flick(earL, -1), 3200);
		setInterval(() => flick(earR, 1), 4100);
	}

	function startGaitLoop(cat) {
		const legFL = cat.querySelector('#legFL');
		const legFR = cat.querySelector('#legFR');
		const legBL = cat.querySelector('#legBL');
		const legBR = cat.querySelector('#legBR');
		const head = cat.querySelector('#head');
		let last = performance.now();
		function loop(now) {
			if (state.exited) return;
			const dt = Math.min(0.05, (now - last) / 1000);
			last = now;
			state.gaitTime += dt;
			const speed = state.orbiting ? 1 : 0.6; // slower when idle/approach
			const phase = state.gaitTime * 8 * speed;
			const a = Math.sin(phase) * 18;
			const b = Math.sin(phase + Math.PI) * 18;
			if (legFL) legFL.style.transform = `rotate(${a}deg)`;
			if (legBR) legBR.style.transform = `rotate(${a}deg)`;
			if (legFR) legFR.style.transform = `rotate(${b}deg)`;
			if (legBL) legBL.style.transform = `rotate(${b}deg)`;

			// subtle head bob when moving
			if (head) {
				const bob = Math.sin(phase * 0.5) * (state.orbiting ? 1.6 : 1.0);
				head.style.transform = `translateY(${bob}px)`;
			}
			state.rafId = requestAnimationFrame(loop);
		}
		state.rafId = requestAnimationFrame(loop);
	}

	function updateHeadOrientation(cat, seg) {
		const head = cat.querySelector('#head');
		if (!head) return;
		// face along path direction: right on top, down on right, left on bottom, up on left
		let rot = 0;
		if (seg === 'top') rot = 0;
		else if (seg === 'right') rot = 90;
		else if (seg === 'bottom') rot = 0; // mirrored by scaleX when facing left
		else if (seg === 'left') rot = -90;
		head.style.transform = `rotate(${rot}deg)`;
	}

	function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

	function moveCatTo(cat, target, durationMs) {
		return new Promise((resolve) => {
			const startX = state.posX;
			const startY = state.posY;
			const dx = target.x - startX;
			const dy = target.y - startY;
			state.facing = dx >= 0 ? 1 : -1;
			const t0 = performance.now();
			function step(now) {
				const t = Math.min(1, (now - t0) / durationMs);
				const e = easeOutCubic(t);
				placeCat(cat, startX + dx * e, startY + dy * e);
				if (t < 1 && !state.exited) requestAnimationFrame(step); else resolve();
			}
			requestAnimationFrame(step);
		});
	}

	function startTrackPatrol(cat) {
		if (state.orbiting) return;
		state.orbiting = true;
		let last = performance.now();
		let progress = 0; // position along top edge in px
		let dir = 1; // 1: right, -1: left
		const speed = 140; // px per second
		const centerOffsetX = 50; // cat half width
		const centerOffsetY = 36; // cat half height
		const margin = 18; // distance above panel top
		let turnUntil = 0; // timestamp until which we pause to "turn"
		function loop(now) {
			if (!state.orbiting || state.exited) return;
			const dt = Math.min(0.05, (now - last) / 1000);
			last = now;
			const rect = getPanelTrackRect(margin);
			const w = rect.width;
			// advance tentative progress
			let nextProgress = progress + dir * speed * dt;
			// bounds detection with turn pause
			if (nextProgress > w) {
				nextProgress = w;
				if (progress !== w) { dir = -1; turnUntil = now + 120; }
			}
			if (nextProgress < 0) {
				nextProgress = 0;
				if (progress !== 0) { dir = 1; turnUntil = now + 120; }
			}
			// apply pause when turning
			if (now < turnUntil) {
				state.facing = dir; // flip immediately during pause
				const xPause = rect.left + nextProgress;
				const yPause = rect.top;
				placeCat(cat, xPause - centerOffsetX, yPause - centerOffsetY);
				requestAnimationFrame(loop);
				return;
			}
			progress = nextProgress;
			const x = rect.left + progress;
			const y = rect.top; // top edge
			state.facing = dir; // face the way we're moving
			placeCat(cat, x - centerOffsetX, y - centerOffsetY);
			requestAnimationFrame(loop);
		}
		requestAnimationFrame(loop);
	}

	function stopOrbit() { state.orbiting = false; }

	function runCatOutRight(cat, durationMs) {
		if (state.exited) return Promise.resolve();
		state.exited = true;
		stopOrbit();
		const startX = state.posX;
		const startY = state.posY;
		const targetX = window.innerWidth + 200;
		const dx = targetX - startX;
		state.facing = 1;
		return new Promise((resolve) => {
			const t0 = performance.now();
			function step(now) {
				const t = Math.min(1, (now - t0) / durationMs);
				const e = easeOutCubic(t);
				placeCat(cat, startX + dx * e, startY);
				if (t < 1) requestAnimationFrame(step); else resolve();
			}
			requestAnimationFrame(step);
		});
	}

	function initCat() {
		const submitBtn = document.getElementById('submitBtn');
		const passInput = document.getElementById('passkey');
		const form = document.getElementById('demoForm');
		if (!submitBtn || !passInput || !form) return;

		const cat = createCatElement();
		document.body.appendChild(cat);
		state.spawned = true;

		// Do not show until typing begins; park offscreen
		placeCat(cat, -9999, -9999, 1);

		// Facial/appendage detail loops
		animateBlink(cat);
		animateTail(cat);
		animateEars(cat);
		startGaitLoop(cat);

		let emerged = false;
		async function emergeFromButton() {
			if (emerged || state.exited) return;
			emerged = true;
			state.emerged = true;
			const spawn = getButtonSpawnPoint();
			placeCat(cat, spawn.x - 50, spawn.y - 20, 1);
			await moveCatTo(cat, getApproachPoint(), 500);
			tryStartOrbit();
		}

		// Trigger emerge only when user starts typing
		passInput.addEventListener('input', () => { if (passInput.value.length > 0) emergeFromButton(); });

		// Start orbit when user is typing any digits and mouse is near the button or field is focused
		let orbitStarted = false;
		function tryStartOrbit() {
			if (orbitStarted || !state.emerged || state.exited) return;
			if (passInput.value.length > 0) {
				orbitStarted = true;
				startTrackPatrol(cat);
			}
		}
		passInput.addEventListener('input', tryStartOrbit);

		// Exit on submit immediately (hit Enter or click)
		form.addEventListener('submit', async () => {
			// Return to button and vanish into it
			stopOrbit();
			const spawn = getButtonSpawnPoint();
			await moveCatTo(cat, { x: spawn.x - 50, y: spawn.y - 20 }, 450);
			cat.animate([
				{ opacity: 1, transform: `translate(${state.posX}px, ${state.posY}px) scaleX(${-state.facing}) scale(1)` },
				{ opacity: 0, transform: `translate(${state.posX}px, ${state.posY}px) scaleX(${-state.facing}) scale(0.6)` }
			], { duration: 220, fill: 'forwards', easing: 'ease-in' });
		}, { once: true });

		// Also exit when success overlay shows (in case of delayed submit handling)
		const overlay = document.getElementById('successOverlay');
		if (overlay) {
			const observer = new MutationObserver((mutations) => {
				for (const m of mutations) {
					if (m.attributeName === 'class' && overlay.classList.contains('show')) {
						// Already handled on submit; ensure cat hidden
						placeCat(cat, -9999, -9999, 1);
					}
				}
			});
			observer.observe(overlay, { attributes: true });
		}
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', initCat);
	} else {
		initCat();
	}
})();

