function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function handleOtpRequest(btnId, statusId, url, modalId) {
    const btn = document.getElementById(btnId);
    const status = document.getElementById(statusId);
    const tokenField = document.querySelector(`#${modalId} [name="cf-turnstile-response"]`);
    const turnstileResponse = tokenField ? tokenField.value : '';

    if (!turnstileResponse) {
        alert('Please complete the security check first!');
        return;
    }

    btn.disabled = true;
    status.innerText = 'Sending...';
    status.className = 'small text-muted';

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken') || '',
        },
        body: `cf_token=${encodeURIComponent(turnstileResponse)}`,
    })
        .then((response) => response.json())
        .then((data) => {
            if (data.status === 'success') {
                status.innerText = 'Code sent!';
                status.className = 'small text-success';
                let count = 60;
                const timer = setInterval(() => {
                    count -= 1;
                    btn.innerText = `Wait (${count}s)`;
                    if (count <= 0) {
                        clearInterval(timer);
                        btn.disabled = false;
                        btn.innerText = 'Get Code';
                    }
                }, 1000);
            } else {
                status.innerText = data.message;
                status.className = 'small text-danger';
                btn.disabled = false;
                if (typeof turnstile !== 'undefined') turnstile.reset();
            }
        })
        .catch(() => {
            status.innerText = 'Error occurred.';
            btn.disabled = false;
        });
}

document.addEventListener('DOMContentLoaded', () => {
    const config = document.getElementById('profile-config');
    if (!config) return;

    const sendPwdBtn = document.getElementById('btnSendPwdOTP');
    const sendDeleteBtn = document.getElementById('btnSendDeleteOTP');

    sendPwdBtn.addEventListener('click', () => {
        handleOtpRequest('btnSendPwdOTP', 'pwdOtpStatus', config.dataset.sendPwdUrl, 'changePasswordModal');
    });

    sendDeleteBtn.addEventListener('click', () => {
        handleOtpRequest('btnSendDeleteOTP', 'otpStatus', config.dataset.sendDeleteUrl, 'deleteAccountModal');
    });

    document.querySelectorAll('.confirm-category-delete-form').forEach((form) => {
        form.addEventListener('submit', (e) => {
            if (!window.confirm('Delete category?')) {
                e.preventDefault();
            }
        });
    });
});
