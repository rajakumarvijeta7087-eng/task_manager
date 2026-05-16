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
});