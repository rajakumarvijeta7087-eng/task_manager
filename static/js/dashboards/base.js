document.addEventListener('DOMContentLoaded', () => {
    const FLASH_DURATION = 4000;
    const FADE_DURATION = 400;

    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(flash => {
        setTimeout(() => {
            flash.classList.add('hide');
            setTimeout(() => {
                flash.remove();
            }, FADE_DURATION);
        }, FLASH_DURATION);

        flash.addEventListener('click', () => {
            flash.classList.add('hide');
            setTimeout(() => flash.remove(), FADE_DURATION);
        });
    });

    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggleBtn = document.getElementById('sidebarToggle');
    
    function openSidebar() { 
        if(sidebar) sidebar.classList.add('open'); 
        if(overlay) overlay.classList.add('active'); 
        document.body.style.overflow = 'hidden';
    }
    
    function closeSidebar() { 
        if(sidebar) sidebar.classList.remove('open'); 
        if(overlay) overlay.classList.remove('active'); 
        document.body.style.overflow = '';
    }
    
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => { 
            if (sidebar && sidebar.classList.contains('open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }
    
    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    function getCsrfToken() { 
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''; 
    }

    function pingLive() { 
        const token = getCsrfToken();
        if(token) {
            fetch('/api/ping', { 
                method: 'POST', 
                headers: { 'X-CSRFToken': token }
            }).catch(err => {}); 
        }
    }
    
    pingLive();
    setInterval(pingLive, 60000);
});