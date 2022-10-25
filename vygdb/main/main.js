import { initWebsocket } from "./wsinit.js";
import { initializer, handler } from "/top/handler.js";

let FONTSIZE = 16;
let EDITOR = null
let CURRENT_FILENAME = null;
let CURRENT_LINE = 0;
let LOOKBACK = -1, COMMAND_HISTORY = [], SEARCH_TEXT = '';
let SOCKET = null; 
let VYGDBADDR = 'ws://localhost:17172'; // HARD CODED IN gdb_client.py
let vygdbdiv = document.querySelector('#vygdbeditor');
let vygdbcommand = document.querySelector('input#vygdbcommand');
let vygdblog = document.querySelector('#vygdblog');
let CONTENTDIV = document.querySelector('flexitem.content');
const SELECTOR = document.querySelector('select.program_selector');
const SEND_BUTTON = document.querySelector('button.send_breakpoint_data');
const ADD_BUTTON = document.querySelector('button.add_program');
let FILES = {};
let ACTIONS = {};
fetch('/top/vdbg_actions.json', { method: 'GET'})
.then(response => { return response.json(); })
.then(response => { 
  ACTIONS = response;
  ADD_BUTTON.disabled = false;
})
.catch(err => { 
  ACTIONS = {};
  ADD_BUTTON.disabled = false;
});

initializer(CONTENTDIV);

window.LOG = ace.edit(vygdblog);
LOG.setTheme("ace/theme/twilight");
LOG.setFontSize(FONTSIZE);
LOG.setReadOnly(true);
function addLogText(text) {
  LOG.session.insert({row: LOG.session.getLength(), column: 0}, "\n" + text);
}

const set_current_file = function(fname, line) {
  if (fname !== CURRENT_FILENAME) {
    if (FILES.hasOwnProperty(fname)) {
      CURRENT_FILENAME = fname;
      EDITOR.setValue(FILES[CURRENT_FILENAME]);
      EDITOR.clearSelection();
      set_current_file(fname, line)
    } else {
      vygdb_send({topic:'vdbg',command:'vtf '+fname});
      if (line != null && line != undefined) CURRENT_LINE = line;  
    }
  } else {
    if (line != null && line != undefined) CURRENT_LINE = line;
    EDITOR.clearSelection();
    EDITOR.gotoLine(CURRENT_LINE, 0);
  }
}

export function vygdb_send(msg) {
  if (SOCKET && SOCKET.readyState === WebSocket.OPEN) {
    SOCKET.send(JSON.stringify(msg)); 
  } else {
    addLogText(`Failed to send message to vygdb SOCKET=${SOCKET} SOCKET.readyState=${(SOCKET) ? SOCKET.readyState : null}`);
  }
}

const save_vdbg_actions = function() {
  fetch('/top/vdbg_actions.json', { 
    method: 'POST',
    headers: new Headers({ 'Content-Type': 'application/json'}),
    body: JSON.stringify(ACTIONS)
  }).catch(err => { console.error(err); });
}

let BREAKPOINT_DATA = [];

let TABLE = document.querySelector('#data_names');

const null_actv_icon = '<i class="fas nullactv text-secondary fa-circle"></i>';
const null_stop_icon = '<i class="fas nullstop text-secondary fa-circle"></i>';
const actv_icon = '<i class="fas actv text-info fa-check-circle"></i>';
const stop_icon = '<i class="fas stop text-info fa-stop-circle"></i>';

let add_replace_program = function(name) {
  ACTIONS.programs[name] = {stops:{},actives:[]};
}

let get_active_program = function() {
  if (!ACTIONS.hasOwnProperty('programs')) ACTIONS.programs = {};
  let program_list = Object.keys(ACTIONS.programs);
  if (program_list.length == 0) {
    add_replace_program('first_program');
    program_list = ['first_program'];
  }
  if (!ACTIONS.hasOwnProperty('active_program') || !ACTIONS.programs.hasOwnProperty(ACTIONS.active_program)) {
    ACTIONS.active_program = program_list[0];
  }
  return ACTIONS.programs[ACTIONS.active_program];
}

const change_breakpoint_status = function(val) {
  save_vdbg_actions();
  redo_tables();
  Object.keys(BREAKPOINT_DATA.breakpoints).forEach(function(key) {
    let bp = BREAKPOINT_DATA.breakpoints[key];
    if (bp.name == val) {
      vygdb_send({topic:'vdbg',command:`vb ${JSON.stringify(bp)}`});
    }
  });
}

const removelst = function(stop_or_active, val) {
  let action = get_active_program();
  if (stop_or_active ==  'active') {
    while (true) {
      var index = action.actives.indexOf(val);
      if (index != -1) {
        action.actives.splice(index, 1);
      } else {
        break;
      }
    }
  } else {
    if (action.stops.hasOwnProperty(val)) {
      if (typeof(action.stops[val]) == "string") {
        action.stops[val] = 'false && ' + action.stops[val].replace('false && ','');
      } else {
        delete action.stops[val];
      }
    }
  }
  change_breakpoint_status(val);
}
const addlst = function(stop_or_active, val) {
  let action = get_active_program();
  if (stop_or_active == 'active') {
    action.actives.push(val);
  } else {
    if (action.stops.hasOwnProperty(val) && typeof(action.stops[val]) == 'string') {
      action.stops[val] = action.stops[val].replace('false && ','');
    } else {
      action.stops[val] = true;
    }
  }
  change_breakpoint_status(val);
}
    
TABLE.querySelector('tbody').addEventListener('dblclick',(e) => {
  if (e.target.tagName == 'TD') {
    let action = get_active_program();
    let val = e.target.dataset['val'];
    let current = action.stops[val];
    if (current && typeof(current) == 'string') {
      if (current.startsWith('false && ')) {
        current = current.replace('false && ','');
      }
    } else {
      current = '';
    }
    let rslt = prompt(`Stop string for breakpoints with name "${val}":`,current);
    action.stops[val] = (rslt.trim() == "") ? true : rslt.trim();
    save_vdbg_actions();
    redo_tables();
  }
})

TABLE.querySelector('tbody').addEventListener('click',(e) => {
  if (e.target.tagName == 'I') {
    let val = e.target.closest('td').dataset['val'];
    if (e.target.classList.contains('stop')) {            removelst('stop', val);    }
    else if (e.target.classList.contains('nullstop')) {   addlst('stop', val);       }
    else if (e.target.classList.contains('actv')) {       removelst('active', val);  }
    else if (e.target.classList.contains('nullactv')) {   addlst('active', val);     }
  }
});

let load_program = function(name) {
  ACTIONS.active_program = name;
  redo_tables();
}

SELECTOR.addEventListener('change',(e) => { load_program(e.target.value); });
SEND_BUTTON.addEventListener('click',(e) => {
  vygdb_send(BREAKPOINT_DATA);
});

ADD_BUTTON.addEventListener('click',(e) => {
  let name = prompt('Enter the name of new debug program');
  get_active_program();
  if (ACTIONS.programs.hasOwnProperty(name)) {
    alert('A program with that name already exists');
  } else if (! /^[a-z0-9_\-]+$/i.test( name ) ) {
    alert('Name must be alphanumeric (dashes and underscores allowed)');
  } else {
    add_replace_program(name);
    load_program(name);
  }
});

let update_status = function(status) {
  SEND_BUTTON.classList.remove('btn-info');
  SEND_BUTTON.disabled = status != 'waiting'; // received|waiting|notconnected
  if (!SEND_BUTTON.disabled) SEND_BUTTON.classList.add('btn-info');
}
update_status('notconnected');

const redo_tables = function() {
  let action = get_active_program();
  SELECTOR.innerHTML = ''
  Object.keys(ACTIONS.programs).forEach(p => {
    SELECTOR.insertAdjacentHTML('beforeend',
      `<option value="${p}" ${(p==ACTIONS.active_program) ? 'selected' : ''}>${p}</option>`);
  });
  let added_list = [];
  let tbody = TABLE.querySelector('tbody');
  tbody.innerHTML = '';
  if (ACTIONS.hasOwnProperty('breakpoints')) {
    Object.keys(ACTIONS.breakpoints).forEach(key => {
      BREAKPOINT_DATA.breakpoints[key] = JSON.parse(JSON.stringify(ACTIONS.breakpoints[key]));
    });
  }

  Object.keys(BREAKPOINT_DATA.breakpoints).forEach(function(key) {
    let bp = BREAKPOINT_DATA.breakpoints[key];
    bp['id'] = key;
    if (bp.name && added_list.indexOf(bp.name) == -1) added_list.push(bp.name);
    bp.stop = false;
    bp.active = bp.name && action.actives.indexOf(bp.name) > -1;
    if (bp.name && action.stops.hasOwnProperty(bp.name)) {
      bp.active = true;
      bp.stop = action.stops[bp.name];
    }
  });

  added_list.sort().forEach(name => {
    let isactv = action.actives.indexOf(name) > -1;
    let suffx = '';
    let isstop = action.stops.hasOwnProperty(name);
    if (isstop && typeof(action.stops[name]) == 'string') {
      suffx = '('+action.stops[name]+')';
      isstop = !action.stops[name].startsWith('false && ');
    }
    let i_stop = (isstop) ? stop_icon : null_stop_icon;
    let i_active = (isstop || isactv) ? actv_icon : null_actv_icon;
    tbody.insertAdjacentHTML('beforeend',`<tr><td data-val="${name}">${i_active} ${i_stop} ${name}${suffx}</td></tr>`);
  })
}

export function vygdb_recv(msg) {
  let d = JSON.parse(msg.data);
  if (d.hasOwnProperty('topic')) {
    if (d.topic == 'vdbg_file') {
      FILES[d.filename] = d.file;
      set_current_file(d.filename, null);
    } else if (d.topic == 'vdbg_current') {
      set_current_file(d.filename, d.hasOwnProperty('line') ? d.line : 0);
    } else if (d.topic == 'vdbg_actions_received') {
      update_status('received');
    } else if (d.topic == 'output') {
      addLogText(d.message);
    } else {
      if (d.topic == 'vdbg_actions') {
        update_status('waiting')
        BREAKPOINT_DATA = d;
        redo_tables();
      } else {
        handler(d.topic, d, vygdb_send, addLogText);
      }
    }
  }
}

let RESTARTBUTTON = document.querySelector('button.restart');

const onClose = function(ev) {
  RESTARTBUTTON.classList.add('btn-info');
  EDITOR.setValue("");
  EDITOR.clearSelection();  
  CURRENT_FILENAME = null;
  addLogText('Socket closed.');
}

let LASTTIMEOUT = null;
const tryconnect = function() {
  if (SOCKET && SOCKET.readyState === WebSocket.OPEN) {
    addLogText('Already connected.');
    return;
  }
  addLogText('Attempting to connect (in 3 seconds) ...');
  if (LASTTIMEOUT) clearTimeout(LASTTIMEOUT);
  LASTTIMEOUT = setTimeout(() => {
    initWebsocket(VYGDBADDR, SOCKET, 500, 1, vygdb_recv, onClose).then(function(socket) { // 500 msec timeout and 1 retry
      SOCKET = socket;
      RESTARTBUTTON.classList.remove('btn-info');
      addLogText('Connected.');
    }).catch(function(err) {
      addLogText('Connection error: '+err);
    });
  }, 3000);
}

vygdbcommand.addEventListener('keydown',function(event) {

  if (event.which === 13 || event.keyCode === 38 || event.keyCode === 40) {
    var val = event.target.value;
    if (event.keyCode === 38 || event.keyCode === 40) {
      if (LOOKBACK === -1) {
        SEARCH_TEXT = val;
      }

      var cmds = COMMAND_HISTORY.filter(function(cmd_) {
        return cmd_.startsWith(SEARCH_TEXT);
      });
      if (cmds.length > 0) {
        LOOKBACK += (event.keyCode === 38) ? 1 : -1;
        LOOKBACK = Math.min(cmds.length - 1, Math.max(0, LOOKBACK));
        event.target.value = cmds[LOOKBACK];
      }

    } else {
      let command = val+'';
      if (val.startsWith('vt ')) {
        try {
          command = 'vt '+JSON.stringify(JSON.parse(val.slice(3)));
        } catch(err) {}
      } else if (val.startsWith('vc ')) {
        let keywords = val.slice(3).trim().split(/\s+/);
        if (keywords.length > 0 && ACTIONS.commands.hasOwnProperty(keywords[0])) {
          command = ACTIONS.commands[keywords[0]]+'';
          for (var ii = 1; ii < keywords.length; ii++) {
            command = command.replace(new RegExp(`\\$${ii-1}`,'g'),keywords[ii]);
          }
        } else {
          return;
        }
      }

      vygdb_send({topic:'vdbg',command:command});
      LOOKBACK = -1;
      if (val.trim().length > 0) {
        COMMAND_HISTORY.unshift(val);
        event.target.value = '';
      }
    }
  } else {
    LOOKBACK = -1;
  }

});

window.step_over = () => { vygdb_send({topic:'vdbg',command:'n'}); }
window.step_into = () => { vygdb_send({topic:'vdbg',command:'s'}); }
window.step_run = () => { vygdb_send({topic:'vdbg',command:'c'}); }
window.restart = () => { fetch('/start_gdb').then(tryconnect); }

EDITOR = ace.edit(vygdbdiv);
EDITOR.setTheme("ace/theme/twilight");
EDITOR.session.setMode("ace/mode/c_cpp");
EDITOR.setFontSize(FONTSIZE);
EDITOR.setReadOnly(true);
EDITOR.renderer.setShowGutter(true);
EDITOR.commands.addCommand({
  name: 'step-over',
  bindKey: {win: 'F10',  mac: 'F10'},
  exec: (editor) => window.step_over(),
});
EDITOR.commands.addCommand({
  name: 'step-into',
  bindKey: {win: 'F9',  mac: 'F9'},
  exec: (editor) => window.step_into(),
});
EDITOR.commands.addCommand({
  name: 'run',
  bindKey: {win: 'F5',  mac: 'F5'},
  exec: (editor) => window.step_run(),
});
EDITOR.on("mouseup",function(evt) {
  let txt = EDITOR.getSelectedText();
  if (txt.length > 0) vygdb_send({topic:'vdbg',command:'v '+txt});
});
EDITOR.setValue('');


let ro = new ResizeObserver(entries => {
  for (let entry of entries) {
    EDITOR.resize();
    EDITOR.setFontSize(FONTSIZE-1);
    EDITOR.setFontSize(FONTSIZE);
    LOG.resize();
    LOG.setFontSize(FONTSIZE-1);
    LOG.setFontSize(FONTSIZE);
  }
});
ro.observe(vygdblog);
