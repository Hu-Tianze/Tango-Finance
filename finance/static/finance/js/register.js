document.addEventListener('DOMContentLoaded', () => {
    const config = document.getElementById('register-config');
    if (!config || typeof window.$ === 'undefined') return;

    const passwordInput = document.getElementById('password');
    const emailInput = document.getElementById('email');
    const nicknameInput = document.getElementById('name');
    const codeInput = document.getElementById('code');
    const submitBtn = document.getElementById('register-submit-btn');
    const rules = {
        length: document.getElementById('rule-length'),
        upper: document.getElementById('rule-upper'),
        lower: document.getElementById('rule-lower'),
        special: document.getElementById('rule-special'),
    };
    const turnstileEnabled = config.dataset.turnstileEnabled === '1';

    let countdown = 60;
    let timer = null;

    function setRuleState(el, ok) {
        if (!el) return;
        el.classList.toggle('valid', ok);
        el.classList.toggle('invalid', !ok);
    }

    function isPasswordValid(password) {
        const checks = {
            length: password.length >= 6,
            upper: /[A-Z]/.test(password),
            lower: /[a-z]/.test(password),
            special: /[^A-Za-z0-9]/.test(password),
        };
        setRuleState(rules.length, checks.length);
        setRuleState(rules.upper, checks.upper);
        setRuleState(rules.lower, checks.lower);
        setRuleState(rules.special, checks.special);
        return checks.length && checks.upper && checks.lower && checks.special;
    }

    function refreshSubmitState() {
        const emailReady = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((emailInput.value || '').trim());
        const nicknameReady = (nicknameInput.value || '').trim().length > 0;
        const codeReady = /^\d{6}$/.test((codeInput.value || '').trim());
        const passwordReady = isPasswordValid(passwordInput.value || '');
        submitBtn.disabled = !(emailReady && nicknameReady && codeReady && passwordReady);
    }

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
        const tokenField = $('[name="cf-turnstile-response"]');
        const hasTurnstileWidget = tokenField.length > 0;
        const cfToken = tokenField.val();

        if (!email) {
            alert('Please enter a valid email address first.');
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

    [passwordInput, emailInput, nicknameInput, codeInput].forEach((el) => {
        el.addEventListener('input', refreshSubmitState);
    });

    const hadPrefilledValues = !!(emailInput.value.trim() || codeInput.value.trim());
    if (hadPrefilledValues) {
        submitBtn.disabled = false;
    } else {
        refreshSubmitState();
    }
});
