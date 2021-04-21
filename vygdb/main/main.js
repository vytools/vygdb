import { initWebsocket } from "./wsinit.js";
import { initializer, handler } from "/top/handler.js";

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
let FILES = {};
initializer(CONTENTDIV);

window.LOG = ace.edit(vygdblog);
LOG.setTheme("ace/theme/twilight");
LOG.setFontSize(16);
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
      vygdb_send({topic:'vygdb',command:'vtf '+fname});
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

export function vygdb_recv(msg) {
  let d = JSON.parse(msg.data);
  if (d.hasOwnProperty('topic')) {
    if (d.topic == 'vygdb_file') {
      FILES[d.filename] = d.file;
      set_current_file(d.filename, null);
    } else if (d.topic == 'vygdb_current') {
      set_current_file(d.filename, d.hasOwnProperty('line') ? d.line : 0);
    } else if (d.topic == 'output') {
      addLogText(d.message);
    } else {
      handler(d.topic, d, vygdb_send, addLogText);
    }
  }
}

let RESTARTBUTTON = document.querySelector('button.restart');

const onClose = function(ev) {
  RESTARTBUTTON.classList.add('btn-danger');
  EDITOR.setValue("");
  EDITOR.clearSelection();  
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
      RESTARTBUTTON.classList.remove('btn-danger');
      addLogText('Connected.');
    }).catch(function(err) {
      addLogText('Connection error: '+err);
    });
  }, 3000);  
}

vygdbcommand.addEventListener('keydown',function(event) {

  if (event.which === 13 || event.keyCode === 38 || event.keyCode === 40) {
    var val = event.target.value;
    if (val.startsWith('vt ')) {
      try {
        val = 'vt '+JSON.stringify(JSON.parse(val.slice(3)));
      } catch(err) {}
    }
    
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
      LOOKBACK = -1;
      vygdb_send({topic:'vygdb',command:val});
      if (val.trim().length > 0) {
        COMMAND_HISTORY.unshift(val);
        event.target.value = '';
      }
    }
  } else {
    LOOKBACK = -1;
  }

});

window.step_over = () => { vygdb_send({topic:'vygdb',command:'n'}); }
window.step_into = () => { vygdb_send({topic:'vygdb',command:'s'}); }
window.step_run = () => { vygdb_send({topic:'vygdb',command:'c'}); }
window.restart = () => { fetch('/start_gdb').then(tryconnect); }

EDITOR = ace.edit(vygdbdiv);
EDITOR.setTheme("ace/theme/twilight");
EDITOR.session.setMode("ace/mode/c_cpp");
EDITOR.setFontSize(16);
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
  if (txt.length > 0) vygdb_send({topic:'vygdb',command:'v '+txt});
});
EDITOR.setValue('');
