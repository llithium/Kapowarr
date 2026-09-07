async function usingApiKey(redirect=true) {
	const key_data = getLocalStorage('api_key', 'last_login');
	const last_login = Number(key_data.last_login) || 0;
	// Login used milliseconds before timestamps were standardized to seconds.
	const last_login_seconds = last_login > 100000000000 ? last_login / 1000 : last_login;

	if (key_data.api_key == null
	|| last_login_seconds < (Date.now() / 1000 - 86400)) {

		return fetch(`${url_base}/api/auth`, {
			'method': 'POST',
			'headers': {'Content-Type': 'application/json'},
			'body': '{}'
		})
			.then(response => {
				if (!response.ok) return Promise.reject(response.status);
				return response.json();
			})
			.then(json => {
				key_data.api_key = json.result.api_key;
				key_data.last_login = Date.now() / 1000;
				setLocalStorage(key_data);
				return json.result.api_key;
			})
			.catch(e => {
				if (e === 401) {
					if (redirect) window.location.href = `${url_base}/login?redirect=${window.location.pathname}`;
					else return null;
				} else {
					console.log(e);
					return null;
				};
			})

	} else {
		return key_data.api_key;
	};
};
