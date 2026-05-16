document.addEventListener('DOMContentLoaded', () => {

    function getCsrfToken() { return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''; }
    
    function csrfFetch(url, options = {}) {
        options.headers = options.headers || {};
        options.headers['X-CSRFToken'] = getCsrfToken();
        options.headers['Content-Type'] = options.headers['Content-Type'] || 'application/json';
        return fetch(url, options);
    }

    function openModal(id) { document.getElementById(id)?.classList.add('show'); }
    function closeModal(id) { document.getElementById(id)?.classList.remove('show'); }

    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.classList.remove('show');
        });
    });

    let currentTaskId = null; 
    let startFileB64 = ''; 
    let endFileB64 = ''; 
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
                if(infoText) infoText.textContent = 'Start your shift by punching in';
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
        e.preventDefault();
        e.target.disabled = true; e.target.textContent = 'Punching in...';
        try {
            const res = await csrfFetch('/api/attendance/punch-in', {method:'POST'});
            const data = await res.json();
            if (res.ok) {
                updateAttendanceUI({is_punched_in: true, punch_in: data.punch_in, punch_out: null, total_minutes: 0});
            } else {
                alert('Error: ' + (data.error || 'Failed to punch in.'));
            }
        } catch(err){ alert('Network error.'); }
        e.target.disabled = false; e.target.innerHTML = '<i class="fas fa-sign-in-alt mr-6"></i>Punch In';
    });

    document.getElementById('btnPunchOut')?.addEventListener('click', async (e) => {
        e.preventDefault();
        e.target.disabled = true; e.target.textContent = 'Punching out...';
        try {
            const res = await csrfFetch('/api/attendance/punch-out', {method:'POST'});
            const data = await res.json();
            if (res.ok) {
                updateAttendanceUI({is_punched_in: false, punch_in: data.punch_in, punch_out: data.punch_out, total_minutes: data.total_minutes});
            } else {
                alert('Error: ' + (data.error || 'Failed to punch out.'));
            }
        } catch(err){ alert('Network error.'); }
        e.target.disabled = false; e.target.innerHTML = '<i class="fas fa-sign-out-alt mr-6"></i>Punch Out';
    });

    document.querySelectorAll('.btn-open-submit-modal').forEach(btn => {
        btn.addEventListener('click', (e) => {
            currentTaskId = e.target.getAttribute('data-task-id');
            const titleEl = document.getElementById('modalTaskTitle');
            const projEl = document.getElementById('modalTaskProject');
            if(titleEl) titleEl.textContent = e.target.getAttribute('data-task-title');
            if(projEl) projEl.textContent = e.target.getAttribute('data-task-proj') || 'No project';
            
            startFileB64 = ''; endFileB64 = '';
            document.getElementById('startFileName')?.classList.add('hide');
            document.getElementById('endFileName')?.classList.add('hide');
            document.getElementById('startZone')?.classList.remove('has-file');
            document.getElementById('endZone')?.classList.remove('has-file');
            
            const now = new Date(); const local = new Date(now - now.getTimezoneOffset() * 60000).toISOString().slice(0,16);
            const startIn = document.getElementById('startTimeInput');
            const endIn = document.getElementById('endTimeInput');
            if(startIn) startIn.value = local;
            if(endIn) endIn.value = local;
            
            document.querySelector('.btn-step[data-step="1"]')?.click();
            openModal('submitModal');
        });
    });

    document.querySelectorAll('.btn-close-submit-modal').forEach(btn => {
        btn.addEventListener('click', () => closeModal('submitModal'));
    });

    document.querySelectorAll('.btn-step').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const n = parseInt(e.target.getAttribute('data-step'));
            document.getElementById('submitStep1')?.classList.toggle('hide', n !== 1);
            document.getElementById('submitStep2')?.classList.toggle('hide', n !== 2);
            document.getElementById('submitStep3')?.classList.toggle('hide', n !== 3);
            
            for (let i = 1; i <= 3; i++) {
                const el = document.getElementById('step' + i);
                if(el) el.className = 'step-item ' + (i < n ? 'done' : i === n ? 'active' : '');
            }

            if(n === 3) {
                const st = document.getElementById('startTimeInput')?.value;
                const et = document.getElementById('endTimeInput')?.value;
                const stText = document.getElementById('reviewStartTime');
                const etText = document.getElementById('reviewEndTime');
                const sfText = document.getElementById('reviewStartFile');
                const efText = document.getElementById('reviewEndFile');
                
                if(stText) stText.textContent = st ? new Date(st).toLocaleString() : '—';
                if(etText) etText.textContent = et ? new Date(et).toLocaleString() : '—';
                if(sfText) sfText.textContent = startFileB64 ? '✓ Uploaded' : 'Not uploaded';
                if(efText) efText.textContent = endFileB64 ? '✓ Uploaded' : 'Not uploaded';
                
                const durEl = document.getElementById('durationDisplay');
                if (st && et && durEl) {
                    const diff = Math.max(0, (new Date(et) - new Date(st)) / 60000);
                    durEl.textContent = `⏱ Duration: ${Math.floor(diff/60)}h ${diff%60}m`;
                }
            }
        });
    });

    document.getElementById('startZone')?.addEventListener('click', () => document.getElementById('startFile')?.click());
    document.getElementById('endZone')?.addEventListener('click', () => document.getElementById('endFile')?.click());

    document.getElementById('startFile')?.addEventListener('change', (e) => {
        const input = e.target; if (!input.files[0]) return;
        const reader = new FileReader();
        reader.onload = ev => {
            startFileB64 = ev.target.result;
            const nameEl = document.getElementById('startFileName');
            if(nameEl) {
                nameEl.textContent = '✓ ' + input.files[0].name;
                nameEl.classList.remove('hide');
            }
            document.getElementById('startZone')?.classList.add('has-file');
        };
        reader.readAsDataURL(input.files[0]);
    });

    document.getElementById('endFile')?.addEventListener('change', (e) => {
        const input = e.target; if (!input.files[0]) return;
        const reader = new FileReader();
        reader.onload = ev => {
            endFileB64 = ev.target.result;
            const nameEl = document.getElementById('endFileName');
            if(nameEl) {
                nameEl.textContent = '✓ ' + input.files[0].name;
                nameEl.classList.remove('hide');
            }
            document.getElementById('endZone')?.classList.add('has-file');
        };
        reader.readAsDataURL(input.files[0]);
    });

    document.getElementById('btnFinalSubmit')?.addEventListener('click', async (e) => {
        e.preventDefault();
        const btn = e.target; 
        btn.disabled = true; 
        btn.textContent = 'Submitting...';
        try {
            const start_time = document.getElementById('startTimeInput')?.value;
            const end_time = document.getElementById('endTimeInput')?.value;
            
            const res = await csrfFetch('/api/task/submit', {
                method: 'POST',
                body: JSON.stringify({
                    task_id: currentTaskId,
                    start_screenshot: startFileB64,
                    end_screenshot: endFileB64,
                    start_time: start_time,
                    end_time: end_time
                })
            });
            const data = await res.json();
            if (res.ok) { 
                closeModal('submitModal'); 
                location.reload(); 
            } else { 
                alert('Error: ' + (data.error || 'Submission failed.')); 
            }
        } catch(err) { 
            alert('Network error.'); 
        }
        btn.disabled = false; 
        btn.innerHTML = '<i class="fas fa-paper-plane mr-6"></i>Submit Task';
    });

});