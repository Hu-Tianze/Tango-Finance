function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

document.addEventListener('DOMContentLoaded', () => {
    const config = document.getElementById('finance-config');
    if (!config) return;

    const transactionModalEl = document.getElementById('transactionModal');
    const transactionModal = new bootstrap.Modal(transactionModalEl);
    const transactionForm = document.getElementById('transactionForm');
    const modalTitle = document.getElementById('modalTitle');
    const submitBtn = document.getElementById('submitBtn');
    const chatWindow = document.getElementById('chat-window');
    const chartLabelsEl = document.getElementById('chart-labels');
    const chartDataEl = document.getElementById('chart-data');
    const chartHintEl = document.getElementById('expenseChartHint');
    const chartCanvasEl = document.getElementById('expenseChart');

    function resetDateTime() {
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        document.getElementById('datetime_now').value = now.toISOString().slice(0, 16);
    }

    function openAddModal() {
        transactionForm.reset();
        transactionForm.action = config.dataset.addUrl;
        modalTitle.innerText = 'New Transaction';
        submitBtn.innerText = 'Save Transaction';
        resetDateTime();
        transactionModal.show();
    }

    function openEditModal(tid) {
        modalTitle.innerText = 'Edit Transaction';
        submitBtn.innerText = 'Update Transaction';
        const editUrl = config.dataset.editTemplate.replace('0', tid);
        transactionForm.action = editUrl;

        fetch(editUrl)
            .then((response) => response.json())
            .then((data) => {
                transactionForm.querySelector('[name="amount"]').value = data.amount;
                transactionForm.querySelector('[name="currency"]').value = data.currency;
                transactionForm.querySelector('[name="type"]').value = data.type;
                transactionForm.querySelector('[name="category"]').value = data.category;
                transactionForm.querySelector('[name="date"]').value = data.date;
                transactionForm.querySelector('[name="note"]').value = data.note;
                transactionModal.show();
            })
            .catch(() => alert('Error fetching data.'));
    }

    function toggleChat() {
        chatWindow.classList.toggle('d-none');
        if (!chatWindow.classList.contains('d-none')) {
            document.getElementById('chat-input').focus();
        }
    }

    function appendMsg(sender, text, id) {
        const container = document.getElementById('chat-messages');
        const wrapper = document.createElement('div');
        wrapper.className = sender === 'user' ? 'user-msg' : 'ai-msg';
        if (id) wrapper.id = id;

        const bubble = document.createElement('div');
        bubble.textContent = text;
        wrapper.appendChild(bubble);
        container.appendChild(wrapper);
        container.scrollTop = container.scrollHeight;
    }

    async function sendMessage() {
        const input = document.getElementById('chat-input');
        const query = input.value.trim();
        if (!query) return;

        appendMsg('user', query);
        input.value = '';
        const loadingId = `ai-${Date.now()}`;
        appendMsg('ai', 'Thinking...', loadingId);

        try {
            const response = await fetch(config.dataset.chatUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') || '',
                },
                body: JSON.stringify({ query }),
            });
            const data = await response.json();
            const loadingNode = document.getElementById(loadingId);
            if (loadingNode) loadingNode.remove();
            if (data.message) {
                appendMsg('ai', data.message);
                if (data.type === 'record') setTimeout(() => window.location.reload(), 2000);
            }
        } catch (e) {
            const loadingNode = document.getElementById(loadingId);
            if (loadingNode) loadingNode.innerText = 'Server error.';
        }
    }

    const labels = chartLabelsEl ? JSON.parse(chartLabelsEl.textContent) : [];
    const chartData = chartDataEl ? JSON.parse(chartDataEl.textContent) : [];
    if (labels.length === 0) {
        chartCanvasEl.style.display = 'none';
        chartHintEl.textContent = 'No expense data for this period.';
    } else {
        const isSingleCategory = labels.length === 1;
        chartHintEl.textContent = isSingleCategory
            ? `All current expenses are in "${labels[0]}".`
            : `${labels.length} categories in this period.`;

        new Chart(chartCanvasEl, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: chartData,
                    backgroundColor: ['#ef476f', '#118ab2', '#ffd166', '#06d6a0', '#8d99ae'],
                    hoverOffset: 4,
                }],
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { position: 'right', display: !isSingleCategory } },
            },
        });
    }

    resetDateTime();

    const params = new URLSearchParams(window.location.search);
    let consumedQueryParam = false;
    if (params.get('quick_add') === '1') {
        openAddModal();
        consumedQueryParam = true;
    }
    if (params.get('open_ai') === '1') {
        if (chatWindow.classList.contains('d-none')) {
            toggleChat();
        }
        consumedQueryParam = true;
    }
    if (consumedQueryParam) {
        const cleanUrl = window.location.pathname + (window.location.hash || '');
        window.history.replaceState({}, '', cleanUrl);
    }

    document.getElementById('openAddModalBtn').addEventListener('click', openAddModal);
    document.querySelectorAll('.edit-transaction-btn').forEach((btn) => {
        btn.addEventListener('click', () => openEditModal(btn.dataset.transactionId));
    });
    document.querySelectorAll('.chat-toggle-btn').forEach((btn) => {
        btn.addEventListener('click', toggleChat);
    });
    document.getElementById('chat-send-btn').addEventListener('click', sendMessage);
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    document.querySelectorAll('.confirm-delete-form').forEach((form) => {
        form.addEventListener('submit', (e) => {
            if (!window.confirm('Are you sure you want to delete this record?')) {
                e.preventDefault();
            }
        });
    });
});
