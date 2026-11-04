(() => {
	const { sessionUrl, sessionProtocol } = document.currentScript.dataset;
	let socket;
	let retry;
	let closing = false;
	let attempts = 0;

	function connect() {
		if (closing || socket) return;
		const connection = new WebSocket(sessionUrl, sessionProtocol);
		socket = connection;
		connection.onopen = () => { if (socket === connection) attempts = 0; };
		connection.onclose = () => {
			if (socket !== connection) return;
			socket = null;
			if (!closing && attempts++ < 8) retry = setTimeout(connect, 500);
		};
	}

	window.addEventListener('pagehide', () => {
		closing = true;
		clearTimeout(retry);
		socket?.close();
		socket = null;
	});
	window.addEventListener('pageshow', () => {
		closing = false;
		connect();
	});
	connect();
})();
