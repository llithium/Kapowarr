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
		classList: { add() {}, remove() {} },
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
