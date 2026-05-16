document.addEventListener('DOMContentLoaded', () => {

    function getCsrfToken() { return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''; }
    
    function csrfFetch(url, options = {}) {
        options.headers = options.headers || {};
        options.headers['X-CSRFToken'] = getCsrfToken();
        if(!(options.body instanceof FormData)) options.headers['Content-Type'] = 'application/json';
        return fetch(url, options);
    }

    function openModal(id) { document.getElementById(id)?.classList.add('show'); }
    function closeModal(id) { document.getElementById(id)?.classList.remove('show'); }

    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.classList.remove('show');
        });
    });

    document.getElementById('btnOpenAssignModal')?.addEventListener('click', () => {
        openModal('assignModal');
    });

    document.querySelectorAll('.btn-close-assign-modal').forEach(btn => {
        btn.addEventListener('click', () => closeModal('assignModal'));
    });

    document.querySelectorAll('.assign-type-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const type = e.target.getAttribute('data-type');
            document.querySelectorAll('.assign-type-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            if (type === 'single') {
                document.getElementById('singleAssignWrap').classList.remove('hide');
                document.getElementById('bulkAssignWrap').classList.add('hide');
            } else {
                document.getElementById('singleAssignWrap').classList.add('hide');
                document.getElementById('bulkAssignWrap').classList.remove('hide');
            }
        });
    });

    document.getElementById('btnSubmitAssign')?.addEventListener('click', async (e) => {
        e.preventDefault();
        const title = document.getElementById('assignTitle')?.value.trim();
        const desc = document.getElementById('assignDesc')?.value.trim();
        const assignedTo = document.getElementById('assignToTasker')?.value;
        const priority = document.getElementById('assignPriority')?.value || 'medium';
        const due = document.getElementById('assignDue')?.value || null;
        
        if (!title || !assignedTo) { 
            alert('Task Title and Assignee are required.'); 
            return; 
        }
        
        const btn = e.target;
        btn.disabled = true; btn.textContent = "Assigning...";
        
        try {
            const res = await csrfFetch('/api/task/assign', {
                method: 'POST',
                body: JSON.stringify({ title, description: desc, assigned_to: parseInt(assignedTo), priority, due_date: due })
            });
            const data = await res.json();
            if (res.ok) { location.reload(); } 
            else { alert('Error: ' + (data.error || 'Failed to assign task.')); }
        } catch(err) { alert('Network error.'); }
        btn.disabled = false; btn.innerHTML = 'Assign Task';
    });

    document.getElementById('btnBulkUpload')?.addEventListener('click', async (e) => {
        e.preventDefault();
        const file = document.getElementById('bulkCsv').files[0];
        if(!file) return alert("Select a CSV file");
        
        const btn = e.target;
        btn.disabled = true; btn.textContent = "Uploading...";
        
        let fd = new FormData(); fd.append('file', file);
        try {
            const res = await csrfFetch('/api/task/bulk_assign', { method: 'POST', body: fd });
            const data = await res.json();
            if (res.ok) { alert(`Successfully assigned ${data.success} tasks.`); location.reload(); }
            else { alert('Error: ' + data.error); }
        } catch(err) { alert('Network error.'); }
        btn.disabled = false; btn.textContent = "Upload & Assign Tasks";
    });

    document.querySelectorAll('.progress-fill').forEach(el => {
        const progress = el.getAttribute('data-progress');
        if (progress) el.style.width = progress + '%';
    });

    let workTimer = null;
    const timeEl = document.getElementById('liveTime');
    const dateEl = document.getElementById('liveDate');
    if (timeEl && dateEl) {
        setInterval(() => {
            const now = new Date();
            timeEl.textContent = now.toLocaleTimeString('en-IN', {hour12: false});
            dateEl.textContent = now.toLocaleDateString('en-IN', {weekday:'long', day:'numeric', month:'long', year:'numeric'});
        }, 1000);
    }
    
    function updateAttendanceUI(data) {
        if (!data) return;
        const dot = document.getElementById('punchDot');
        const statusText = document.getElementById('punchStatusText');
        const infoText = document.getElementById('punchInfo');
        const btnIn = document.getElementById('btnPunchIn');
        const btnOut = document.getElementById('btnPunchOut');
        const workDisplay = document.getElementById('workingTimeDisplay');
        
        if (data.is_punched_in) {
            dot?.classList.add('active');
            if(statusText) statusText.textContent = 'Currently Working';
            if(infoText) infoText.textContent = 'Punched in at ' + (data.punch_in || '');
            btnIn?.classList.add('hide'); btnOut?.classList.remove('hide');
            startWorkTimer(data.punch_in);
        } else {
            dot?.classList.remove('active');
            if (data.punch_out) {
                if(statusText) statusText.textContent = 'Shift Complete';
                if(infoText) infoText.textContent = data.punch_in + ' → ' + data.punch_out;
                const mins = data.total_minutes || 0;
                if(workDisplay) workDisplay.textContent = 'Worked: ' + Math.floor(mins/60) + 'h ' + (mins%60) + 'm';
            } else {
                if(statusText) statusText.textContent = 'Not Punched In';
                if(infoText) infoText.textContent = 'Start shift by punching in';
            }
            btnIn?.classList.remove('hide'); btnOut?.classList.add('hide');
            if (workTimer) clearInterval(workTimer);
        }
    }
    
    function startWorkTimer(punchInStr) {
        if (workTimer) clearInterval(workTimer);
        const display = document.getElementById('workingTimeDisplay');
        if(!display) return;
        workTimer = setInterval(() => {
            const now = new Date();
            const start = new Date(now.toISOString().split('T')[0] + 'T' + punchInStr);
            const diffMs = now - start;
            if (diffMs < 0) return;
            const tSec = Math.floor(diffMs / 1000);
            display.textContent = `Working: ${String(Math.floor(tSec/3600)).padStart(2,'0')}:${String(Math.floor((tSec%3600)/60)).padStart(2,'0')}:${String(tSec%60).padStart(2,'0')}`;
        }, 1000);
    }
    
    if (document.getElementById('attendanceCard')) {
        csrfFetch('/api/attendance/status').then(res => res.json()).then(data => {
            if(!data.error) updateAttendanceUI(data);
        }).catch(err => console.log(err));
    }
    
    document.getElementById('btnPunchIn')?.addEventListener('click', async (e) => {
        e.preventDefault(); e.target.disabled = true; e.target.textContent = 'Punching in...';
        try {
            const res = await csrfFetch('/api/attendance/punch-in', {method:'POST'});
            const data = await res.json();
            if (res.ok) updateAttendanceUI({is_punched_in: true, punch_in: data.punch_in, punch_out: null, total_minutes: 0});
            else alert(data.error || 'Failed to punch in.');
        } catch(err){ alert('Network error.'); }
        e.target.disabled = false; e.target.innerHTML = '<i class="fas fa-sign-in-alt mr-6"></i>Punch In';
    });
    
    document.getElementById('btnPunchOut')?.addEventListener('click', async (e) => {
        e.preventDefault(); e.target.disabled = true; e.target.textContent = 'Punching out...';
        try {
            const res = await csrfFetch('/api/attendance/punch-out', {method:'POST'});
            const data = await res.json();
            if (res.ok) updateAttendanceUI({is_punched_in: false, punch_in: data.punch_in, punch_out: data.punch_out, total_minutes: data.total_minutes});
            else alert(data.error || 'Failed to punch out.');
        } catch(err){ alert('Network error.'); }
        e.target.disabled = false; e.target.innerHTML = '<i class="fas fa-sign-out-alt mr-6"></i>Punch Out';
    });
});