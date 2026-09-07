const HistoryEls = {
	table: document.querySelector('#history'),
	page_turner: {
		previous: document.querySelector('#previous-page'),
		next: document.querySelector('#next-page'),
		number: document.querySelector('#page-number')
	},
	buttons: {
		refresh: document.querySelector('#refresh-button'),
		clear: document.querySelector('#clear-button')
	},
	entry: document.querySelector('.pre-build-els .history-entry')
};

var offset = 0;

function fillHistory(api_key) {
	fetchAPI('/activity/history', api_key, {offset: offset})
	.then(json => {
		HistoryEls.table.innerHTML = '';
        document.querySelector('#activity-message').textContent = json.result.length ? '' : (offset ? 'No more entries.' : 'No downloads yet.');
        HistoryEls.page_turner.previous.disabled = offset === 0;
        HistoryEls.page_turner.next.disabled = json.result.length < 50;
		json.result.forEach(obj => {
			const entry = HistoryEls.entry.cloneNode(true);

			const title = entry.querySelector('a');
            title.href = obj.web_link;
			title.innerText = obj.web_title;
            title.title = obj.web_title;
            if (obj.web_sub_title !== null)
                title.title += `\n\n${obj.web_sub_title}`;

            if (obj.file_title !== null) {
                const vol_link = entry.querySelector('td:nth-child(2) a')
                vol_link.innerText = obj.file_title;
                if (obj.volume_id !== null)
                    vol_link.href = `${url_base}/volumes/${obj.volume_id}`;
            };

            if (obj.source !== null)
                entry.querySelector('td:nth-child(3)').innerText = obj.source;

			let d = new Date(obj.downloaded_at * 1000);
			let formatted_date = d.toLocaleString('en-CA').slice(0,10) + ' ' + d.toTimeString().slice(0,5);
			entry.querySelector('td:nth-child(4)').innerText = formatted_date;
			
			if (obj.success !== null)
				entry.querySelector('td:nth-child(5)').innerText =
					obj.success ? 'Success' : 'Failed';

			HistoryEls.table.appendChild(entry);
		});
	}).catch(() => {
        document.querySelector('#activity-message').textContent = 'Couldn’t load entries. Use Refresh to try again.';
    });
};

function clearHistory(api_key) {
    if (!window.confirm('Clear the complete history?')) return;
    sendAPI('DELETE', '/activity/history', api_key).then(() => {
        offset = 0;
        HistoryEls.page_turner.number.innerText = 'Page 1';
        fillHistory(api_key);
    }).catch(() => {
        document.querySelector('#activity-message').textContent = 'Couldn’t clear entries. Try again.';
    });
};

function reduceOffset(api_key) {
	if (offset === 0) return;
	offset--;
	HistoryEls.page_turner.number.innerText = `Page ${offset + 1}`;
	fillHistory(api_key);
};

function increaseOffset(api_key) {
	if (HistoryEls.table.innerHTML === '') return;
	offset++;
	HistoryEls.page_turner.number.innerText = `Page ${offset + 1}`;
	fillHistory(api_key);
};

// code run on load
usingApiKey()
.then(api_key => {
	fillHistory(api_key);
	HistoryEls.buttons.refresh.onclick = e => fillHistory(api_key);
	HistoryEls.buttons.clear.onclick = e => clearHistory(api_key);
	HistoryEls.page_turner.previous.onclick = e => reduceOffset(api_key);
	HistoryEls.page_turner.next.onclick = e => increaseOffset(api_key);
});
