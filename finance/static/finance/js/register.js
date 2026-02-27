document.addEventListener('DOMContentLoaded', () => {
    const config = document.getElementById('register-config');
    if (!config || typeof window.$ === 'undefined') return;

    let countdown = 60;
    let timer = null;

    function setCountdown() {
        const btn = $('#send-btn');
        if (countdown === 0) {
            btn.prop('disabled', false);
            btn.text('Get a One-Time Code');
            countdown = 60;
            clearInterval(timer);
            return;
        }
        btn.prop('disabled', true);
        btn.text(`Resend in ${countdown}s`);
        countdown -= 1;
    }

    $('#send-btn').click(() => {
        const email = $('#email').val();
        const cfToken = $('[name="cf-turnstile-response"]').val();

        if (!email) {
            alert('Please enter a valid email address first.');
            return;
        }

        if (!cfToken) {
            alert('Please complete the security check first!');
            return;
        }

        const btn = $('#send-btn');
        btn.prop('disabled', true).text('Verifying...');

        $.post(config.dataset.sendCodeUrl, {
            email,
            cf_token: cfToken,
            csrfmiddlewaretoken: config.dataset.csrfToken,
        }, (data) => {
            if (data.status === 'success') {
                alert('Code sent! Please check your email.');
                timer = setInterval(setCountdown, 1000);
            } else {
                alert(`Error: ${data.message || 'Failed to send code.'}`);
                btn.prop('disabled', false).text('Get a One-Time Code');
                if (typeof turnstile !== 'undefined') turnstile.reset();
            }
        }).fail(() => {
            alert('Server error. Please try again later.');
            btn.prop('disabled', false).text('Get a One-Time Code');
        });
    });
});
