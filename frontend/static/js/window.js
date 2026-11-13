let window_trigger = null;
const window_root = document.querySelector('.window');
const background_inert = new Map();

function openWindow() {
	return window_root.hasAttribute('show-window')
		? window_root.querySelector('section[show-window]') : null;
};

function windowFocusTargets(window) {
	return [...window.querySelectorAll(
		'a[href], button, input, select, textarea, summary, [tabindex]'
	)].filter(el => el.tabIndex >= 0 && !el.matches(':disabled')
		&& el.getClientRects().length > 0
		&& getComputedStyle(el).visibility !== 'hidden');
};

function focusWindow(window) {
	(windowFocusTargets(window)[0] || window).focus();
};

function showWindow(id) {
	// A loading state or a second dialog belongs to the same modal session.
	if (!openWindow()) {
		window_trigger = document.activeElement;
		for (const el of document.body.children) {
			if (el === window_root || !(el instanceof HTMLElement)) continue;
			background_inert.set(el, el.inert);
			el.inert = true;
		}
	}
	document.querySelectorAll('.window > section').forEach(window => {
		window.removeAttribute('show-window');
	});
	const selected_window = document.getElementById(id);
	selected_window.setAttribute('show-window', '');
	window_root.setAttribute('show-window', '');
	focusWindow(selected_window);
};

function showLoadWindow(id) {
	const loading_window = document.getElementById(id).dataset.loading_window;
	if (loading_window) showWindow(loading_window);
};

function closeWindow() {
	window_root.removeAttribute('show-window');
	for (const [el, inert] of background_inert) el.inert = inert;
	background_inert.clear();
	if (window_trigger instanceof HTMLElement && window_trigger.isConnected) {
		if (window_trigger.getClientRects().length > 0) window_trigger.focus();
		if (document.activeElement !== window_trigger) {
			// A responsive disclosure may hide the original trigger during the dialog.
			const disclosure = window_trigger.closest('details');
			if (disclosure) focusWindow(disclosure);
			else document.querySelector('main')?.focus();
		}
	}
	window_trigger = null;
};

// Contain keyboard and programmatic focus while the background is unavailable.
document.addEventListener('keydown', e => {
	const window = openWindow();
	if (!window) return;
	if (e.key === 'Escape') {
		e.preventDefault();
		e.stopPropagation();
		closeWindow();
	} else if (e.key === 'Tab') {
		const targets = windowFocusTargets(window);
		const first = targets[0];
		const last = targets.at(-1);
		if (!first) {
			e.preventDefault();
			window.focus();
		} else if (document.activeElement === window
			|| !window.contains(document.activeElement)
			|| (e.shiftKey && document.activeElement === first)
			|| (!e.shiftKey && document.activeElement === last)) {
			e.preventDefault();
			(e.shiftKey ? last : first).focus();
		}
	}
}, true);

document.addEventListener('focusin', e => {
	const window = openWindow();
	if (window && !window.contains(e.target)) focusWindow(window);
});

window_root.onclick = e => {
	if (e.target === window_root) closeWindow();
};

document.querySelectorAll(
	'.window > section :where(button[title="Close"], button.cancel-window)'
).forEach(button => {
	button.onclick = () => closeWindow();
});
