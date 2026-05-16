document.addEventListener('DOMContentLoaded', () => {
    function getCsrfToken() { 
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''; 
    }
    
    function csrfFetch(url, options = {}) {
        options.headers = options.headers || {};
        options.headers['X-CSRFToken'] = getCsrfToken();
        options.headers['Content-Type'] = options.headers['Content-Type'] || 'application/json';
        return fetch(url, options);
    }
    
    const btnUpdateProfile = document.getElementById('btnUpdateProfile');
    
    if (btnUpdateProfile) {
        btnUpdateProfile.addEventListener('click', async (e) => {
            e.preventDefault();
            
            const usernameInput = document.getElementById('profUsername');
            const jobTitleInput = document.getElementById('profJobTitle');
            const currentPwdInput = document.getElementById('profCurrentPwd');
            const newPwdInput = document.getElementById('profNewPwd');

            const username = usernameInput ? usernameInput.value.trim() : '';
            const job_title = jobTitleInput ? jobTitleInput.value.trim() : '';
            const current_password = currentPwdInput ? currentPwdInput.value : '';
            const new_password = newPwdInput ? newPwdInput.value : '';

            if (!username || username.length < 3) {
                alert("Error: Full Name must be at least 3 characters long.");
                return;
            }

            if (new_password && new_password.length < 8) {
                alert("Error: New Password must be at least 8 characters long.");
                return;
            }

            if (new_password && !current_password) {
                alert("Error: You must enter your Current Password to set a New Password.");
                return;
            }

            const btn = e.target;
            btn.disabled = true;
            btn.textContent = 'Updating...';

            try {
                const res = await csrfFetch('/api/profile/update', {
                    method: 'POST',
                    body: JSON.stringify({ 
                        username, 
                        job_title, 
                        current_password, 
                        new_password 
                    })
                });
                
                const data = await res.json();
                
                if (res.ok) {
                    alert('Profile updated successfully!');
                    if (currentPwdInput) currentPwdInput.value = '';
                    if (newPwdInput) newPwdInput.value = '';
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Failed to update profile.'));
                }
            } catch(err) {
                alert('Network error. Please check your connection and try again.');
            }
            
            btn.disabled = false;
            btn.textContent = 'Save Changes';
        });
    }
});