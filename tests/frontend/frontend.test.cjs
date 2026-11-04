const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const root = `${__dirname}/../..`;
const read = (file) => fs.readFileSync(`${root}/${file}`, 'utf8');

function context(overrides = {}) {
	const values = new Map();
	return {
		localStorage: {
			getItem: (key) => values.get(key) ?? null,
			setItem: (key, value) => values.set(key, String(value))
		},
		Date,
		URLSearchParams,
		console,
		...overrides
	};
}

test('desktop browser lifetime follows page close and back-forward restoration', () => {
	const listeners = new Map();
	const connections = [];
	const retries = new Map();
	class BrowserSocket {
		constructor(url, protocol) {
			assert.equal(url, 'ws://127.0.0.1:1234/');
			assert.equal(protocol, 'session-token');
			connections.push(this);
		}
		close() { this.closed = true; }
	}
	vm.runInNewContext(read('frontend/static/js/desktop.js'), {
		document: { currentScript: { dataset: {
			sessionUrl: 'ws://127.0.0.1:1234/', sessionProtocol: 'session-token'
		} } },
		window: { addEventListener: (event, callback) => listeners.set(event, callback) },
		WebSocket: BrowserSocket,
		setTimeout: (callback) => { const id = retries.size + 1; retries.set(id, callback); return id; },
		clearTimeout: (id) => retries.delete(id)
	});
	assert.equal(connections.length, 1);
	listeners.get('pagehide')();
	assert.equal(connections[0].closed, true);
	listeners.get('pageshow')();
	assert.equal(connections.length, 2);
	connections[0].onclose(); // A delayed event from the page's previous connection.
	assert.equal(retries.size, 0);
	connections[1].onclose();
	assert.equal(retries.size, 1);
	[...retries.values()][0]();
	assert.equal(connections.length, 3);
	listeners.get('pagehide')();
	assert.equal(connections[2].closed, true);
});

test('shared storage repairs missing and invalid values', () => {
	const ctx = context();
	vm.runInNewContext(read('frontend/static/js/storage.js'), ctx);
	ctx.localStorage.setItem('kapowarr', '{invalid');
	vm.runInNewContext("setLocalStorage({theme: 'dark'})", ctx);
	assert.deepEqual(
		JSON.parse(
			JSON.stringify(
				vm.runInNewContext("getLocalStorage('theme', 'api_key')", ctx)
			)
		),
		{ theme: 'dark', api_key: null }
	);
	for (const invalid of ['null', '[]', 'false']) {
		ctx.localStorage.setItem('kapowarr', invalid);
		assert.equal(
			vm.runInNewContext("getLocalStorage('api_key').api_key", ctx),
			null
		);
	}
});

test('general API URL builder encodes query values', () => {
	const makeElement = () => ({
		dataset: { value: '/kapowarr' },
		classList: { add() {}, remove() {}, toggle() {} },
		querySelectorAll: () => [],
		setAttribute() {},
		focus() {}
	});
	const ctx = context({
		url_base: '/kapowarr',
		window: { location: { pathname: '/other' } },
		document: {
			querySelector: () => makeElement(),
			querySelectorAll: () => [],
			addEventListener() {}
		},
		usingApiKey: () => new Promise(() => {}),
		io: () => ({ on() {}, connect() {} }),
		setTimeout
	});
	vm.runInNewContext(
		read('frontend/static/js/storage.js') +
			read('frontend/static/js/general.js'),
		ctx
	);
	assert.equal(
		vm.runInNewContext(
			"buildAPIUrl('/volumes/search', 'a&b', {query: 'Saga & Batman', offset: 2})",
			ctx
		),
		'/kapowarr/api/volumes/search?api_key=a%26b&query=Saga+%26+Batman&offset=2'
	);
});

test('usingApiKey handles fresh storage and legacy millisecond timestamps', async () => {
	const ctx = context({
		url_base: '/kapowarr',
		Date: { now: () => 1700000000000 },
		fetch: async () => ({
			ok: true,
			json: async () => ({ result: { api_key: 'fresh-key' } })
		})
	});
	vm.runInNewContext(
		read('frontend/static/js/storage.js') + read('frontend/static/js/auth.js'),
		ctx
	);
	assert.equal(
		await vm.runInNewContext('usingApiKey(false)', ctx),
		'fresh-key'
	);
	assert.equal(
		JSON.parse(ctx.localStorage.getItem('kapowarr')).last_login,
		1700000000
	);
	ctx.localStorage.setItem(
		'kapowarr',
		JSON.stringify({ api_key: 'existing', last_login: 1699999999000 })
	);
	ctx.fetch = async () => {
		throw new Error('legacy key unexpectedly refreshed');
	};
	assert.equal(await vm.runInNewContext('usingApiKey(false)', ctx), 'existing');
	ctx.localStorage.setItem(
		'kapowarr',
		JSON.stringify({
			api_key: 'expired',
			last_login: 1699800000000,
			theme: 'dark'
		})
	);
	ctx.fetch = async () => ({
		ok: true,
		json: async () => ({ result: { api_key: 'renewed' } })
	});
	assert.equal(await vm.runInNewContext('usingApiKey(false)', ctx), 'renewed');
	assert.equal(JSON.parse(ctx.localStorage.getItem('kapowarr')).theme, 'dark');
});

test('login script can load with shared storage and authentication stubs', async () => {
	const makeElement = () => ({
		dataset: { value: '/kapowarr' },
		classList: { add() {}, remove() {} },
		focus() {},
		action: ''
	});
	const ctx = context({
		url_base: '/kapowarr',
		Date: { now: () => 1700000000000 },
		window: { location: { pathname: '/login', search: '', href: '' } },
		document: { querySelector: (selector) => makeElement() },
		fetch: async (url) =>
			url.endsWith('/api/auth')
				? { ok: true, json: async () => ({ result: { api_key: 'key' } }) }
				: {
						ok: true,
						json: async () => ({ result: { authentication_method: 1 } })
					}
	});
	vm.runInNewContext(
		read('frontend/static/js/storage.js') +
			read('frontend/static/js/auth.js') +
			read('frontend/static/js/login.js'),
		ctx
	);
	await new Promise((resolve) => setImmediate(resolve));
	assert.equal(JSON.parse(ctx.localStorage.getItem('kapowarr')).api_key, 'key');
});

function element() {
	const classes = new Set();
	return {
		dataset: {},
		innerText: '',
		value: '',
		classList: {
			add: (...names) => names.forEach((name) => classes.add(name)),
			remove: (...names) => names.forEach((name) => classes.delete(name)),
			contains: (name) => classes.has(name)
		},
		querySelector: () => element(),
		querySelectorAll: () => [],
		remove() {},
		cloneNode: () => element(),
		appendChild() {},
		setAttribute() {},
		focus() {},
		onclick: null
	};
}

function loadDownloadClients(ctx, elements = new Map()) {
	ctx.document = {
		querySelector: (selector) => elements.get(selector) || element(),
		querySelectorAll: () => []
	};
	ctx.usingApiKey = () => new Promise(() => {});
	ctx.fetchAPI = () => new Promise(() => {});
	ctx.hide = (toHide, toShow = []) => {
		toHide.forEach((e) => e.classList.add('hidden'));
		toShow.forEach((e) => e.classList.remove('hidden'));
	};
	ctx.showWindow = () => {};
	vm.runInNewContext(
		read('frontend/static/js/settings_download_clients.js'),
		ctx
	);
}

test('torrent test reports both success and failure states', async () => {
	const elements = new Map([
		['#add-error', element()],
		['#add-torrent-form tbody', element()],
		['#test-torrent-add', element()]
	]);
	elements.get('#add-torrent-form tbody').dataset.type = 'qbit';
	elements.get('#add-torrent-form tbody').querySelector = () => ({
		value: 'value'
	});
	const ctx = context({
		sendAPI: async () => ({
			json: async () => ({ result: { success: true, description: '' } })
		})
	});
	loadDownloadClients(ctx, elements);
	assert.equal(await vm.runInNewContext('testAddTorrent("key")', ctx), true);
	assert.equal(elements.get('#add-error').classList.contains('hidden'), true);
	ctx.sendAPI = async () => ({
		json: async () => ({ result: { success: false, description: 'bad' } })
	});
	assert.equal(await vm.runInNewContext('testAddTorrent("key")', ctx), false);
	assert.equal(elements.get('#add-error').innerText, 'bad');
	assert.equal(elements.get('#add-error').classList.contains('hidden'), false);
});

test(
	'remote mapping deletion waits for success and preserves rows on failure',
	{ timeout: 1000 },
	async () => {
		const row = element();
		const error = element();
		let removed = false;
		row.remove = () => {
			removed = true;
		};
		const ctx = context();
		loadDownloadClients(
			ctx,
			new Map([
				['#remote-mapping-list > tr[data-id="4"]', row],
				['#remote-mapping-error', error]
			])
		);
		ctx.usingApiKey = async () => 'key';
		let resolveDelete;
		const response = new Promise((resolve) => {
			resolveDelete = resolve;
		});
		let requestStarted;
		const started = new Promise((resolve) => {
			requestStarted = resolve;
		});
		ctx.sendAPI = () => {
			requestStarted();
			return response;
		};
		const deletion = vm.runInNewContext('deleteRemoteMapping(4)', ctx);
		await started;
		assert.equal(removed, false);
		resolveDelete({});
		await deletion;
		assert.equal(removed, true);

		removed = false;
		ctx.sendAPI = async () => {
			throw new Error('failed');
		};
		await vm.runInNewContext('deleteRemoteMapping(4)', ctx);
		assert.equal(removed, false);
		assert.equal(error.innerText, 'Failed to delete remote path mapping');
		assert.equal(error.classList.contains('hidden'), false);
	}
);

function libraryContext(overrides = {}) {
	const elements = new Map();
	const element = selector => {
		if (!elements.has(selector)) elements.set(selector, {
			value: '', checked: false, style: {}, dataset: {},
			classList: { add() {}, remove() {}, toggle() {} },
			querySelector: child => element(`${selector} ${child}`),
			querySelectorAll: () => [],
			hasAttribute: () => false
		});
		return elements.get(selector);
	};
	const ctx = context({
		document: { querySelector: element },
		hide: (_, visible) => { ctx.visible = visible[0]; },
		window: { confirm: () => false },
		...overrides
	});
	vm.createContext(ctx);
	vm.runInContext(read('frontend/static/js/volumes.js').split('// code run on load')[0], ctx);
	vm.runInContext('populateLibrary = () => {}; updateSelection = () => {};', ctx);
	return { ctx, element, run: code => vm.runInContext(code, ctx) };
}

test('library search ignores old responses and recovers from a failed request', async () => {
	const pending = [];
	const { ctx, element, run } = libraryContext({
		fetchAPI: () => new Promise((resolve, reject) => pending.push({ resolve, reject }))
	});
	run("fetchLibrary('key')");
	element('#search-input').value = 'new query';
	run("fetchLibrary('key')");
	pending[1].resolve({ result: [] });
	await new Promise(setImmediate);
	assert.equal(element('#library-empty-title').textContent, 'No matching comics');
	pending[0].resolve({ result: [{ id: 1 }] });
	await new Promise(setImmediate);
	assert.equal(ctx.visible, element('#empty-library'));
	run("fetchLibrary('key')");
	pending[2].reject(new Error('Offline'));
	await new Promise(setImmediate);
	assert.equal(ctx.visible, element('#library-error'));
	run("fetchLibrary('key')");
	pending[3].resolve({ result: [{ id: 1 }] });
	await new Promise(setImmediate);
	assert.equal(ctx.visible, element('#library-container'));
});

test('bulk actions require a selection and deletion requires confirmation', () => {
	let calls = 0;
	const { element, run } = libraryContext({ sendAPI: () => { calls++; } });
	run("runAction('key', 'delete')");
	assert.equal(calls, 0);
	element('#table-library').querySelectorAll = () => [{ parentNode: { parentNode: { dataset: { id: '1' } } } }];
	run("runAction('key', 'delete', {delete_folder: true})");
	assert.equal(calls, 0);
});

test('volumes with no issues have a finite progress bar', () => {
	const { element, run } = libraryContext();
	run("new LibraryEntry(1, 'key').setProgressBar(0, 0)");
	assert.equal(element('#list-library .vol-1 .list-prog-bar').style.width, '0%');
	assert.equal(element('#list-library .vol-1 .list-prog-container').title, 'No issues');
});

test('download events update retained data before either view exists', () => {
	const { element, run } = libraryContext();
	element('#list-library').querySelector = () => null;
	element('#table-library').querySelector = () => null;
	run(`libraryVolumes.set(1, {id: 1, issue_count: 3, issues_downloaded: 1});
		updateDownloadedStatus({volume_id: 1, downloaded_issues: [2], not_downloaded_issues: []}, 'key');`);
	assert.equal(run('libraryVolumes.get(1).issues_downloaded'), 2);
	run("updateDownloadedStatus({volume_id: 99, downloaded_issues: [2], not_downloaded_issues: []}, 'key')");
	assert.equal(run('libraryVolumes.size'), 1);
});

test('monitoring updates retained state with only the table rendered', async () => {
	const { element, run } = libraryContext({
		sendAPI: async () => ({}),
		setIcon: (button, icon, label) => { button.textContent = label; },
		icons: { monitored: 'yes', unmonitored: 'no' }
	});
	element('#list-library').querySelector = () => null;
	run('libraryVolumes.set(1, {id: 1, monitored: true, issue_count: 3, issues_downloaded: 1})');
	await run("new LibraryEntry(1, 'key').setMonitored(false)");
	assert.equal(run('libraryVolumes.get(1).monitored'), false);
	assert.equal(element('#table-library .vol-1 .table-monitored').textContent, 'Unmonitored');
	assert.equal(element('#table-library .vol-1 .table-prog-bar').style.backgroundColor, 'var(--error-color)');
});

test('API requests preserve multipart bodies and reject unauthorized responses', async () => {
	const element = () => ({
		dataset: {value: ''},
		classList: {add() {}, remove() {}, toggle() {}},
		querySelectorAll: () => [],
		setAttribute() {}
	});
	const ctx = context({
		FormData,
		window: {location: {pathname: '/system/backups'}},
		document: {
			querySelector: element,
			querySelectorAll: () => [],
			addEventListener() {}
		},
		usingApiKey: () => new Promise(() => {}),
		fetch: async (url, options) => { ctx.request = {url, options}; return {ok: true}; }
	});
	vm.runInNewContext(read('frontend/static/js/storage.js') + read('frontend/static/js/general.js'), ctx);
	ctx.form = new FormData();
	ctx.form.append('file', new Blob(['database']), 'backup.db');
	await vm.runInNewContext("sendAPI('POST', '/system/database', 'key', {}, form)", ctx);
	assert.equal(ctx.request.options.body, ctx.form);
	assert.equal(ctx.request.options.headers, undefined);
	assert.equal(ctx.request.options.body.get('file').name, 'backup.db');
	ctx.fetch = async () => ({ok: false, status: 401});
	for (const request of ["fetchAPI('/settings', 'key')", "sendAPI('DELETE', '/settings', 'key')"]) {
		await assert.rejects(vm.runInNewContext(request, ctx), error => error.status === 401);
		assert.equal(ctx.window.location.href, '/login?redirect=/system/backups');
	}
});

test('import selection excludes disabled conflict rows from submission', async () => {
	const source = read('frontend/static/js/library_import.js');
	const selection = source.slice(source.indexOf('function toggleSelectAll()'), source.indexOf('function openEditCVMatch('));
	const submission = source.slice(source.indexOf('function importLibrary('), source.indexOf('// code run on load'));
	const normal = {checked: false, disabled: false};
	const conflict = {checked: false, disabled: true};
	const rows = [normal, conflict].map((checkbox, rowid) => ({
		dataset: {rowid: String(rowid)}, querySelector: () => checkbox
	}));
	const list = {querySelectorAll: selector => selector.startsWith('tr:') ? rows.filter(row => row.querySelector().checked) : [normal, conflict]};
	const ctx = context({
		LIEls: {select_all: {checked: true}, proposal_list: list, views: {list: {}, loading: {}, start: {}}, buttons: {}, conflict_notice: {}},
		rowid_to_filepath: {0: {cv_id: 1, filepath: 'good'}, 1: {cv_id: 2, filepath: 'conflict'}},
		setLibraryImportLoadingMode() {}, hide() {},
		sendAPI: async (...args) => { ctx.payload = args[4]; return {json: async () => ({result: {conflicts: []}})}; }
	});
	vm.runInNewContext(selection + submission, ctx);
	vm.runInNewContext('toggleSelectAll()', ctx);
	assert.equal(normal.checked, true);
	assert.equal(conflict.checked, false);
	conflict.checked = true;
	await vm.runInNewContext("importLibrary('key')", ctx);
	await new Promise(resolve => setImmediate(resolve));
	assert.deepEqual(JSON.parse(JSON.stringify(ctx.payload)), [{filepath: 'good', id: 1}]);
});

test('queue move uses the row position after another download ends', () => {
	const source = read('frontend/static/js/queue.js');
	const addEntry = source.slice(source.indexOf('function addQueueEntry('), source.indexOf('function updateQueueEntry('));
	const children = [];
	const nodes = [];
	const createEntry = () => {
		const elements = new Map();
		const entry = {dataset: {}, querySelector(selector) {
			if (!elements.has(selector)) elements.set(selector, {});
			return elements.get(selector);
		}};
		nodes.push(entry);
		return entry;
	};
	const moves = [];
	const ctx = context({
		url_base: '', QEls: {queue: {children, appendChild: entry => children.push(entry)}, queue_entry: {cloneNode: createEntry}},
		updateQueueEntry() {}, moveEntry: (...args) => moves.push(args), deleteEntry() {}
	});
	vm.runInNewContext(addEntry, ctx);
	for (const id of [1, 2, 3]) {
		ctx.item = {id, title: 'Issue', volume_id: 1, source_name: 'test', web_link: '', web_title: '', web_sub_title: null};
		vm.runInNewContext("addQueueEntry('key', item)", ctx);
	}
	children.shift();
	nodes[2].querySelector('.move-up-dl').onclick();
	assert.deepEqual(moves[0], [3, 0, 'key']);
});

test('API key rotation stores the new credential before reloading the page', async () => {
	const source = read('frontend/static/js/settings_general.js');
	const rotate = source.slice(source.indexOf('function generateApiKey('), source.indexOf('// code run on load'));
	const calls = [];
	const ctx = context({
		sendAPI: async () => ({json: async () => ({result: {api_key: 'new-key'}})}),
		setLocalStorage: value => calls.push(['storage', value.api_key]),
		window: {location: {reload: () => calls.push(['reload'])}}
	});
	vm.runInNewContext(rotate, ctx);
	vm.runInNewContext("generateApiKey('old-key')", ctx);
	await new Promise(resolve => setImmediate(resolve));
	assert.deepEqual(calls, [['storage', 'new-key'], ['reload']]);
});
