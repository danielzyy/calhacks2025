# hcp_ui.py
"""
Lightweight Flask + SocketIO UI for HCP server
Run: python hcp_ui.py
Dependencies: flask flask_socketio eventlet
    pip install flask flask_socketio eventlet
"""
import eventlet
eventlet.monkey_patch()

import time
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hcp-ui-secret'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

DEVICES = {}
REQ_LOG = []

INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HCP Visualizer</title>
  <style>
    :root {
      --bg:#0b0f14; --card:#111823; --muted:#94a3b8; --accent:#7c5cff;
      --glass:rgba(255,255,255,0.03); --border:rgba(255,255,255,0.06);
    }
    html,body {
      height:100%;margin:0;font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto;
      background:var(--bg);color:#e2e8f0;overflow:hidden;
    }
    .app {display:grid;grid-template-columns:320px 1fr 400px;gap:16px;padding:16px;height:100%}
    .panel {
      background:var(--card);border-radius:12px;padding:14px;
      box-shadow:0 6px 16px rgba(0,0,0,0.5);overflow:hidden;display:flex;flex-direction:column;
    }
    h1 {font-size:16px;margin:0 0 4px;color:#fff;font-weight:600}
    .small {font-size:12px;color:var(--muted)}
    .devices-list {display:flex;flex-direction:column;gap:6px;margin-top:10px;overflow-y:auto}
    .device-row {
      display:flex;align-items:center;justify-content:space-between;
      padding:8px 10px;border-radius:8px;background:var(--glass);
      cursor:pointer;transition:0.2s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
    }
    .device-row:hover {background:rgba(124,92,255,0.15)}
    .device-name {font-weight:600;font-size:14px;overflow:hidden;text-overflow:ellipsis}
    .device-desc {font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis}
    .node-canvas {flex:1;border-radius:10px;background:linear-gradient(180deg,rgba(255,255,255,0.02),transparent);position:relative}
    svg {width:100%;height:100%}
    .chip {background:rgba(255,255,255,0.04);padding:6px 8px;border-radius:8px;font-size:13px}
    .btn {background:var(--accent);border:none;padding:8px 10px;border-radius:8px;color:white;cursor:pointer;font-size:13px}
    .controls {display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
    .log {flex:1;overflow-y:auto;font-size:13px;padding-right:4px}
    .req {padding:8px;border-radius:8px;background:rgba(255,255,255,0.03);margin-bottom:6px;word-wrap:break-word}
    .status-ok {color:#9be7a2}.status-err {color:#ff9b9b}
  </style>
</head>
<body>
  <div class="app">
    <div class="panel">
      <h1>Devices</h1>
      <div class="small">Registered hardware nodes</div>
      <div class="devices-list" id="devicesList"></div>
    </div>

    <div class="panel">
      <div class="controls">
        <div class="chip">HCP-Augmented LLM</div>
        <button class="btn" id="centerBtn">Center</button>
      </div>
      <div class="node-canvas" id="canvas"><svg id="svgRoot"></svg></div>
    </div>

    <div class="panel">
      <h1>Request / Response Log</h1>
      <div class="small">Live command and response stream</div>
      <div class="log" id="log"></div>
    </div>
  </div>

<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<script>
  const socket = io();
  let devices = {};
  const svg = document.getElementById('svgRoot');
  const devicesList = document.getElementById('devicesList');
  const logEl = document.getElementById('log');

  function addLog(txt, status){
    const d = document.createElement('div');
    d.className='req';
    d.innerHTML=txt;
    if(status) d.classList.add(status==='ok'?'status-ok':'status-err');
    logEl.prepend(d);
  }

  function renderDevices(){
    svg.innerHTML='';
    const w = svg.clientWidth, h = svg.clientHeight;
    const cx = w/2, cy = h/2;

    // Center LLM node
    const llm = document.createElementNS('http://www.w3.org/2000/svg','g');
    const circle = document.createElementNS('http://www.w3.org/2000/svg','circle');
    circle.setAttribute('cx',cx);circle.setAttribute('cy',cy);
    circle.setAttribute('r',48); // slightly larger center node
    circle.setAttribute('fill','none');
    circle.setAttribute('stroke','#7c5cff');
    circle.setAttribute('stroke-width','1.8');
    llm.appendChild(circle);
    const text = document.createElementNS('http://www.w3.org/2000/svg','text');
    text.setAttribute('x',cx);text.setAttribute('y',cy+5);
    text.setAttribute('text-anchor','middle');
    text.setAttribute('fill','white');
    text.setAttribute('font-size','13');
    text.textContent='HCP LLM';
    llm.appendChild(text);
    svg.appendChild(llm);

    const keys = Object.keys(devices);
    keys.forEach((id,i)=>{
      const angle=(i/keys.length)*2*Math.PI;
      const dist=180+(keys.length*6);
      const x=cx+Math.cos(angle)*dist;
      const y=cy+Math.sin(angle)*dist;

      // connecting line
      const line=document.createElementNS('http://www.w3.org/2000/svg','line');
      line.setAttribute('x1',cx);line.setAttribute('y1',cy);
      line.setAttribute('x2',x);line.setAttribute('y2',y);
      line.setAttribute('stroke','rgba(255,255,255,0.06)');
      line.setAttribute('stroke-width','1');
      line.setAttribute('id','line-'+id);
      svg.appendChild(line);

      // node group
      const g=document.createElementNS('http://www.w3.org/2000/svg','g');
      g.setAttribute('transform',`translate(${x-50},${y-28})`);
      g.setAttribute('data-id',id);

      const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
      rect.setAttribute('width',100);
      rect.setAttribute('height',56);
      rect.setAttribute('rx',10);
      rect.setAttribute('fill','rgba(255,255,255,0.03)');
      rect.setAttribute('stroke','rgba(255,255,255,0.08)');
      rect.setAttribute('id','node-'+id);
      g.appendChild(rect);

      // multi-line text wrapping
      const label = devices[id].device_id;
      const maxLineLength = 12;
      const lines = [];
      for (let i=0; i<label.length; i+=maxLineLength){
        lines.push(label.slice(i, i+maxLineLength));
        if (lines.length === 2) break; // max 2 lines
      }

      const textEl = document.createElementNS('http://www.w3.org/2000/svg','text');
      textEl.setAttribute('x',50);
      textEl.setAttribute('y',lines.length === 1 ? 33 : 26);
      textEl.setAttribute('text-anchor','middle');
      textEl.setAttribute('fill','white');
      textEl.setAttribute('font-size','11');
      textEl.setAttribute('font-family','Inter, sans-serif');

      lines.forEach((lineText, idx)=>{
        const tspan = document.createElementNS('http://www.w3.org/2000/svg','tspan');
        tspan.setAttribute('x',50);
        tspan.setAttribute('dy', idx === 0 ? 0 : 12);
        tspan.textContent = lineText;
        textEl.appendChild(tspan);
      });

      g.appendChild(textEl);
      svg.appendChild(g);
    });

    renderDevicesList();
  }

  function renderDevicesList(){
    devicesList.innerHTML='';
    Object.values(devices).forEach(d=>{
      const row=document.createElement('div');
      row.className='device-row';
      row.onclick=()=>showActions(d);
      row.innerHTML=`
        <div style="overflow:hidden">
          <div class="device-name">${d.device_id}</div>
          <div class="device-desc">${d.freetext_desc||''}</div>
        </div>`;
      devicesList.appendChild(row);
    });
  }

  function showActions(device){
    const items=Object.keys(device.available_commands||{});
    let html=`<div style='padding:16px;font-family:Inter;color:#e2e8f0;background:#0b0f14;'>
      <h3 style='margin-top:0;color:white'>${device.device_id}</h3>
      <div style='color:#94a3b8;font-size:13px;margin-bottom:10px'>${device.freetext_desc||''}</div>`;
    if(items.length==0){ html+='<div class="small">No available actions</div>'; }
    else{
      items.forEach(k=>{
        html+=`<div style='margin-top:6px'><b>${k}</b>
          <div class='small'>${JSON.stringify(device.available_commands[k])}</div></div>`;
      });
    }
    html+='</div>';
    const w=window.open('', '_blank', 'width=420,height=400');
    w.document.write(html);
  }

  socket.on('connect', ()=>{
    fetch('/api/devices').then(r=>r.json()).then(j=>{devices=j;renderDevices();});
  });
  socket.on('register_device',(d)=>{
    devices[d.device_id]=d; renderDevices();
    addLog(`<b>Registered</b> ${d.device_id}`);
  });
  socket.on('request',(r)=>{
    addLog(`<b>REQ</b> ${r.request_id} → ${r.target_hardware}: ${JSON.stringify(r.command_body)}`);
    const line=document.getElementById('line-'+r.target_hardware);
    if(line){line.setAttribute('stroke','rgba(124,92,255,0.9)');setTimeout(()=>line.setAttribute('stroke','rgba(255,255,255,0.06)'),800);}
  });
  socket.on('response',(r)=>{
    addLog(`<b>RES</b> ${r.request_id} ← ${r.target_hardware}: ${JSON.stringify(r.payload)}`, r.status);
    const line=document.getElementById('line-'+r.target_hardware);
    if(line){line.setAttribute('stroke','rgba(92,255,124,0.9)');setTimeout(()=>line.setAttribute('stroke','rgba(255,255,255,0.06)'),1000);}
  });

  document.getElementById('centerBtn').onclick=()=>renderDevices();
  window.addEventListener('resize',()=>renderDevices());
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/api/register_device', methods=['POST'])
def api_register():
    data = request.get_json(force=True)
    if not data or 'device_id' not in data:
        return jsonify({'error':'missing device_id'}), 400
    device_id = data['device_id']
    DEVICES[device_id] = {
        'device_id': device_id,
        'freetext_desc': data.get('freetext_desc',''),
        'addr': data.get('addr'),
        'available_commands': data.get('available_commands',{})
    }
    socketio.emit('register_device', DEVICES[device_id])
    return jsonify({'ok':True})

@app.route('/api/devices', methods=['GET'])
def api_devices():
    return jsonify(DEVICES)

@app.route('/api/log_request', methods=['POST'])
def api_log_request():
    data = request.get_json(force=True)
    req_id = data.get('request_id', str(uuid.uuid4()))
    entry = {'request_id': req_id, 'target_hardware': data.get('target_hardware'),
             'toolname': data.get('toolname'), 'command_body': data.get('command_body'),
             'ts': time.time()}
    REQ_LOG.append(entry)
    socketio.emit('request', entry)
    return jsonify({'ok':True, 'request_id': req_id})

@app.route('/api/log_response', methods=['POST'])
def api_log_response():
    data = request.get_json(force=True)
    entry = {'request_id': data.get('request_id'), 'target_hardware': data.get('target_hardware'),
             'status': data.get('status','ok'), 'payload': data.get('payload'), 'ts': time.time()}
    REQ_LOG.append(entry)
    socketio.emit('response', entry)
    return jsonify({'ok':True})

@socketio.on('ui_request')
def handle_ui_request(data):
    socketio.emit('request', data)
    emit('ack', {'ok':True, 'request_id': data.get('request_id')})

if __name__ == '__main__':
    print('Starting HCP visualizer on http://127.0.0.1:5000')
    socketio.run(app, host='0.0.0.0', port=5000)
