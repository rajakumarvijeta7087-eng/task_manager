document.addEventListener('DOMContentLoaded', () => {
    function getCsrfToken() { return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''; }
    function csrfFetch(url, options = {}) {
        options.headers = options.headers || {};
        options.headers['X-CSRFToken'] = getCsrfToken();
        if(!(options.body instanceof FormData)) options.headers['Content-Type'] = 'application/json';
        return fetch(url, options);
    }

    // TABS LOGIC
    document.querySelectorAll('.admin-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
            e.target.classList.add('active');
            const targetId = e.target.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
        });
    });

    document.querySelectorAll('.btn-del-user').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            if(!confirm("Delete user permanently?")) return;
            await csrfFetch('/api/admin/delete_user', { method:'POST', body:JSON.stringify({user_id: e.target.dataset.id})});
            location.reload();
        });
    });

    document.getElementById('btnSaveSettings')?.addEventListener('click', async () => {
        await csrfFetch('/api/admin/settings', { method:'POST', body:JSON.stringify({
            domains: document.getElementById('adminDomains').value,
            whitelist_mode: document.getElementById('adminWlMode').value
        })});
        alert('Settings Saved');
    });

    document.getElementById('btnUploadWl')?.addEventListener('click', async () => {
        const file = document.getElementById('wlFile').files[0];
        if(!file) return alert("Select a CSV file");
        let fd = new FormData(); fd.append('file', file);
        await csrfFetch('/api/admin/whitelist', { method:'POST', body:fd });
        alert('Whitelist Uploaded');
    });

    document.getElementById('btnSendMail')?.addEventListener('click', async (e) => {
        const email = document.getElementById('mailTo').value.trim();
        const subject = document.getElementById('mailSub').value.trim();
        const body = document.getElementById('mailBody').value.trim();
        if (!email || !subject || !body) return alert('Please fill in all email fields.');
        const btn = e.target; btn.disabled = true; btn.textContent = 'Sending...';
        try {
            const res = await csrfFetch('/api/admin/send_email', { method:'POST', body:JSON.stringify({ email, subject, body }) });
            if (res.ok) { alert('Email Sent Successfully!'); location.reload(); } 
            else { const data = await res.json(); alert('Error: ' + (data.error || 'Failed to send.')); }
        } catch(err) { alert('Network error.'); }
        btn.disabled = false; btn.textContent = 'Send Email';
    });

    document.getElementById('btnQuickAddUser')?.addEventListener('click', async (e) => {
        const username = document.getElementById('quickAddName').value.trim();
        const email = document.getElementById('quickAddEmail').value.trim();
        const role = document.getElementById('quickAddRole').value;
        if (!username || !email) return alert('Name and Email are required.');
        const btn = e.target; btn.disabled = true; btn.textContent = 'Creating...';
        try {
            const res = await csrfFetch('/api/admin/add_user', { method: 'POST', body: JSON.stringify({ username, email, role }) });
            if (res.ok) { alert('User added! They can now log in to set their password.'); location.reload(); } 
            else { const data = await res.json(); alert('Error: ' + (data.error || 'Failed.')); }
        } catch(err) { alert('Network error.'); }
        btn.disabled = false; btn.textContent = 'Create User';
    });
});