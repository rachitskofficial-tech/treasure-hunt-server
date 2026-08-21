from flask import jsonify, request, redirect, render_template, make_response
from app import app, get_db, admin_required, MESSAGES, ROUTES, ROUTE_LABELS, get_team_from_cookie, record_live_scan, team_gate_response


def ensure_qr_messages():
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS qr_messages (route TEXT PRIMARY KEY, message TEXT NOT NULL)')
    for route in ROUTES:
        db.execute('INSERT OR IGNORE INTO qr_messages(route, message) VALUES (?, ?)', (route, MESSAGES.get(route, '')))
    db.commit()
    return db


def current_message(route):
    row = ensure_qr_messages().execute('SELECT message FROM qr_messages WHERE route=?', (route,)).fetchone()
    return row['message'] if row else MESSAGES.get(route, '')


@app.route('/admin/qr-messages', methods=['GET', 'POST'])
@admin_required
def admin_qr_messages():
    db = ensure_qr_messages()
    if request.method == 'POST':
        for route in ROUTES:
            if route in request.form:
                db.execute('UPDATE qr_messages SET message=? WHERE route=?', (request.form.get(route, ''), route))
        db.commit()
        return redirect('/admin')
    return jsonify({route: {'label': ROUTE_LABELS.get(route, route), 'message': current_message(route), 'url': request.host_url.rstrip('/') + '/event/' + route, 'preview_url': request.host_url.rstrip('/') + '/admin/qr-preview/' + route} for route in ROUTES})


@app.route('/admin/qr-preview/<route>')
@admin_required
def admin_qr_preview(route):
    if route not in ROUTES:
        return 'QR route not found', 404
    response = make_response(render_template('message.html', title=ROUTE_LABELS[route], message=current_message(route)))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def live_event_scan_with_editable_message(route):
    team = get_team_from_cookie()
    if not team:
        return team_gate_response()
    record_live_scan(route, team)
    response = make_response(render_template('message.html', title=ROUTE_LABELS[route], message=current_message(route)))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


for _route in ROUTES:
    _endpoint = f'event_{_route}'
    if _endpoint in app.view_functions:
        app.view_functions[_endpoint] = (lambda route: (lambda: live_event_scan_with_editable_message(route)))(_route)


QR_EDITOR = r'''
<style>
.qr-editor-panel{margin-top:18px;border-radius:22px;padding:20px;background:#101827;border:1px solid #24314b}.qr-editor-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:16px}.qr-editor-title{margin:0;color:#fff;font-size:22px;font-weight:900}.qr-editor-desc{margin:5px 0 0;color:#8f9ab5;font-size:11px;line-height:1.5}.qr-editor-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.qr-editor-item{padding:13px;border:1px solid #24314b;border-radius:15px;background:#0d1324}.qr-editor-label{display:block;color:#dce4f6;font-size:11px;font-weight:900;margin-bottom:8px}.qr-editor-input{width:100%;box-sizing:border-box;min-height:72px;resize:vertical;padding:10px;border-radius:10px;border:1px solid #2b3856;background:#080d18;color:#fff;font:inherit;font-size:12px;line-height:1.45}.qr-editor-url{display:block;margin-top:9px;color:#7db7ff;font-family:monospace;font-size:10px;word-break:break-all}.qr-editor-links{display:flex;gap:8px;flex-wrap:wrap}.qr-editor-open{display:inline-block;margin-top:8px;padding:7px 9px;border:1px solid #344768;border-radius:9px;background:#18233a;color:#dbe8ff;text-decoration:none;font-size:10px;font-weight:900}.qr-editor-preview{border-color:#24513e;background:#10251c;color:#7df2bd}.qr-editor-actions{display:flex;justify-content:flex-end;margin-top:14px;gap:8px}.qr-editor-save{padding:11px 16px;border:1px solid #24513e;border-radius:11px;background:#173428;color:#7df2bd;font-weight:900;cursor:pointer}.qr-editor-status{font-size:10px;color:#7f8ba6;align-self:center}@media(max-width:760px){.qr-editor-grid{grid-template-columns:1fr}}
</style>
<section class="qr-editor-panel" id="qr-editor-panel">
<div class="qr-editor-head"><div><h2 class="qr-editor-title">✏️ QR Message Editor</h2><p class="qr-editor-desc">Edit the message, preview the exact current message, or open the live QR page. QR links and scan tracking remain unchanged.</p></div></div>
<form method="post" action="/admin/qr-messages" id="qr-editor-form"><div class="qr-editor-grid" id="qr-editor-grid"><div class="qr-editor-item">Loading QR messages…</div></div><div class="qr-editor-actions"><span class="qr-editor-status" id="qr-editor-status"></span><button class="qr-editor-save" type="submit">Save QR Messages</button></div></form>
</section>
<script>
(async()=>{const grid=document.getElementById('qr-editor-grid'),status=document.getElementById('qr-editor-status');try{const r=await fetch('/admin/qr-messages?ts='+Date.now(),{cache:'no-store',credentials:'same-origin'});if(!r.ok)throw new Error();const data=await r.json();grid.innerHTML=Object.entries(data).map(([route,v])=>{const item=document.createElement('div');item.className='qr-editor-item';const label=document.createElement('label');label.className='qr-editor-label';label.textContent=v.label;const ta=document.createElement('textarea');ta.className='qr-editor-input';ta.name=route;ta.maxLength=500;ta.value=v.message||'';const url=document.createElement('a');url.className='qr-editor-url';url.href=v.url;url.target='_blank';url.rel='noopener noreferrer';url.textContent=v.url;const links=document.createElement('div');links.className='qr-editor-links';const preview=document.createElement('a');preview.className='qr-editor-open qr-editor-preview';preview.href=v.preview_url;preview.target='_blank';preview.rel='noopener noreferrer';preview.textContent='Preview Message ↗';const live=document.createElement('a');live.className='qr-editor-open';live.href=v.url;live.target='_blank';live.rel='noopener noreferrer';live.textContent='Live QR Page ↗';links.append(preview,live);item.append(label,ta,url,links);return item.outerHTML}).join('');status.textContent='Loaded';}catch(e){grid.innerHTML='<div class="qr-editor-item">Could not load QR messages. Refresh the admin panel.</div>';status.textContent='Load failed';}})();
</script>
'''


@app.after_request
def inject_qr_editor(response):
    if request.path == '/admin' and response.content_type and 'text/html' in response.content_type and response.status_code == 200:
        try:
            body = response.get_data(as_text=True)
            if 'id="qr-editor-panel"' not in body and '</body>' in body:
                response.set_data(body.replace('</body>', QR_EDITOR + '</body>'))
        except Exception:
            pass
    return response
