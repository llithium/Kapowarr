let window_trigger = null;

function focusWindow(window) {
	const focus_target = window.querySelector(
		'input:not([disabled]), select:not([disabled]), button:not([disabled]), a[href]'
	) || window;
	focus_target.focus();
};

function showWindow(id) {
	window_trigger = document.activeElement;
	// Deselect all windows
	document.querySelectorAll('.window > section').forEach(window => {
		window.removeAttribute('show-window');
	});

	// Select the correct window
	const selected_window = document.querySelector(`.window > section#${id}`);
	selected_window.setAttribute('show-window', '');

	// Show the window
	document.querySelector('.window').setAttribute('show-window', '');
	focusWindow(selected_window);
};

function showLoadWindow(id) {
	window_trigger = document.activeElement;
	// Deselect all windows
	document.querySelectorAll('.window > section').forEach(window => {
		window.removeAttribute('show-window');
	});

	// Select the correct window
	const loading_window = document.querySelector(`.window > section#${id}`).dataset.loading_window;
	if (loading_window !== undefined) {
		const selected_window = document.querySelector(`.window > section#${loading_window}`);
		selected_window.setAttribute('show-window', '');
		focusWindow(selected_window);
	};

	// Show the window
	document.querySelector('.window').setAttribute('show-window', '');
};

function closeWindow() {
	document.querySelector('.window').removeAttribute('show-window');
	if (window_trigger instanceof HTMLElement) window_trigger.focus();
};

// code run on load

document.querySelector('body').onkeydown = e => {
	if (
		e.code === "Escape"
		&&
		document.querySelector('.window[show-window]')
	) {
		e.stopImmediatePropagation();
		closeWindow();
	};
};

document.querySelector('.window').onclick = e => {
	e.stopImmediatePropagation();
	closeWindow();
};

document.querySelectorAll('.window > section').forEach(
	el => el.onclick = e => e.stopImmediatePropagation()
);

document.querySelectorAll(
	'.window > section :where(button[title="Cancel"], button.cancel-window)'
).forEach(e => {
	e.onclick = f => closeWindow();
});
