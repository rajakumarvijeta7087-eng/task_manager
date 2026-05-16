document.addEventListener('DOMContentLoaded', () => {
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(flash => {
        setTimeout(() => {
            flash.classList.add('hide');
            setTimeout(() => flash.remove(), 300);
        }, 3000);
        flash.addEventListener('click', () => {
            flash.classList.add('hide');
            setTimeout(() => flash.remove(), 300);
        });
    });

    const toggleNewPwBtn = document.getElementById('toggleNewPwBtn');
    const newPwInput = document.getElementById('new_password');
    if (toggleNewPwBtn && newPwInput) {
        toggleNewPwBtn.addEventListener('click', () => {
            if (newPwInput.type === 'password') {
                newPwInput.type = 'text';
                toggleNewPwBtn.textContent = 'Hide';
            } else {
                newPwInput.type = 'password';
                toggleNewPwBtn.textContent = 'Show';
            }
        });
    }

    const toggleConfirmPwBtn = document.getElementById('toggleConfirmPwBtn');
    const confirmPwInput = document.getElementById('confirm_password');
    if (toggleConfirmPwBtn && confirmPwInput) {
        toggleConfirmPwBtn.addEventListener('click', () => {
            if (confirmPwInput.type === 'password') {
                confirmPwInput.type = 'text';
                toggleConfirmPwBtn.textContent = 'Hide';
            } else {
                confirmPwInput.type = 'password';
                toggleConfirmPwBtn.textContent = 'Show';
            }
        });
    }

    const pwInput = document.getElementById('new_password');
    const pwBtn = document.getElementById('submitBtn');
    if (pwInput && pwBtn) {
        pwInput.addEventListener('input', function() {
            const v = this.value;
            const checks = {
                'hint-len': v.length >= 8,
                'hint-upper': /[A-Z]/.test(v),
                'hint-num': /[0-9]/.test(v),
                'hint-special': /[^A-Za-z0-9]/.test(v)
            };
            let allOk = true;
            for (const [id, ok] of Object.entries(checks)) {
                const el = document.getElementById(id);
                if (el) {
                    el.classList.toggle('ok', ok);
                    const icon = el.querySelector('i');
                    if (icon) icon.className = ok ? 'fas fa-check' : 'fas fa-circle';
                }
                if (!ok) allOk = false;
            }
            pwBtn.disabled = !allOk;
        });
    }

    const digits = document.querySelectorAll('.otp-digit');
    const hidden = document.getElementById('otpHidden');

    if (digits.length > 0 && hidden) {
        digits.forEach((d, i) => {
            d.addEventListener('input', () => {
                d.value = d.value.replace(/\D/g, '');
                if (d.value && i < digits.length - 1) digits[i+1].focus();
                hidden.value = [...digits].map(x => x.value).join('');
            });
            d.addEventListener('keydown', e => {
                if (e.key === 'Backspace' && !d.value && i > 0) digits[i-1].focus();
            });
            d.addEventListener('paste', e => {
                e.preventDefault();
                const cb = e.clipboardData || window.clipboardData;
                if (!cb) return;
                const paste = cb.getData('text').replace(/\D/g,'').slice(0,6);
                paste.split('').forEach((ch, j) => { if (digits[j]) digits[j].value = ch; });
                if (digits[paste.length - 1]) digits[paste.length - 1].focus();
                hidden.value = [...digits].map(x => x.value).join('');
            });
        });
    }
});