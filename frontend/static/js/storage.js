const default_values = {
	lib_sorting: 'title',
	lib_view: 'posters',
	lib_filter: '',
	theme: 'light',
	translated_filter: 'all',
	api_key: null,
	last_login: 0,
	monitor_new_volume: true,
	monitor_new_issues: true,
	monitoring_scheme: 'all'
};

function readLocalStorage() {
	let storage;
	try {
		storage = JSON.parse(localStorage.getItem('kapowarr') || '{}');
	} catch (e) {
		storage = {};
	}
	if (storage === null || typeof storage !== 'object' || Array.isArray(storage))
		storage = {};

	return {...default_values, ...storage};
};

function setupLocalStorage() {
	localStorage.setItem('kapowarr', JSON.stringify(readLocalStorage()));
};

function getLocalStorage(...keys) {
	const storage = readLocalStorage();
	return Object.fromEntries(keys.map(key => [key, storage[key]]));
};

function setLocalStorage(keys_values) {
	const storage = readLocalStorage();
	Object.assign(storage, keys_values);
	localStorage.setItem('kapowarr', JSON.stringify(storage));
};
