document.addEventListener('DOMContentLoaded', () => {
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(flash => {
        setTimeout(() => {
            flash.classList.add('hide');
            setTimeout(() => flash.remove(), 400);
        }, 4000);
        flash.addEventListener('click', () => {
            flash.classList.add('hide');
            setTimeout(() => flash.remove(), 400);
        });
    });

    const toggleBtn = document.getElementById('togglePasswordBtn');
    const pwdInput = document.getElementById('password');
    if (toggleBtn && pwdInput) {
        toggleBtn.addEventListener('click', () => {
            if (pwdInput.type === 'password') {
                pwdInput.type = 'text';
                toggleBtn.textContent = 'Hide';
            } else {
                pwdInput.type = 'password';
                toggleBtn.textContent = 'Show';
            }
        });
    }

    const usernameInput = document.getElementById('username');
    const feedback = document.getElementById('usernameFeedback');
    const btnDetails = document.getElementById('detailsBtn');
    const csrfToken = document.getElementById('csrfToken')?.value;
    let timer;

    if (usernameInput && feedback && btnDetails) {
        usernameInput.addEventListener('input', function() {
            clearTimeout(timer);
            const val = this.value.trim();
            if (val.length < 3) {
                feedback.style.display = 'none';
                btnDetails.disabled = false;
                return;
            }
            btnDetails.disabled = true;
            feedback.style.display = 'flex';
            feedback.style.color = 'var(--text-muted)';
            feedback.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
            
            timer = setTimeout(() => {
                fetch('/api/auth/check-username', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ username: val })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'available') {
                        feedback.style.color = 'var(--primary)';
                        feedback.innerHTML = '<i class="fas fa-check"></i> ' + data.message;
                        btnDetails.disabled = false;
                    } else {
                        feedback.style.color = 'var(--error)';
                        feedback.innerHTML = '<i class="fas fa-xmark"></i> ' + data.message;
                        btnDetails.disabled = true;
                    }
                })
                .catch(() => {
                    feedback.style.display = 'none';
                    btnDetails.disabled = false;
                });
            }, 500);
        });
    }

    const pwInput = document.getElementById('password');
    const pwBtn = document.getElementById('pwBtn');
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

    const otpForm = document.getElementById('otpForm');
    const otpSubmitBtn = document.getElementById('otpSubmitBtn');
    if (otpForm && otpSubmitBtn) {
        otpForm.addEventListener('submit', (e) => {
            otpSubmitBtn.disabled = true;
            otpSubmitBtn.innerHTML = 'Verifying... <i class="fas fa-spinner fa-spin"></i>';
        });
    }
});