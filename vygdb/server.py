from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
import os, logging, threading, subprocess, json
from pathlib import Path
BASEPATH = os.path.dirname(os.path.realpath(__file__))
vygdbpath = os.path.join(BASEPATH,'gdb_client.py')
global THREAD
THREAD = None

def _restart(cmd):
  global THREAD
  if THREAD is None or not THREAD.is_alive():
    THREAD = threading.Thread(target=subprocess.run, daemon=True, args=(cmd,))
    THREAD.start()
  else:
    print('Thread still running', flush=True)

def sendx(self, typ, c):
  self.send_response(200)
  self.send_header('Content-type',typ)
  self.end_headers()
  self.wfile.write(c)

def newpath(self,p,k,v):
  if p.startswith('/'+k+'/') and '..' not in p:
    pp = p.replace('/'+k,v,1)
    if os.path.isfile(pp):
      if pp.endswith('.html'):
        sendx(self, 'text/html', Path(pp).read_text().encode())
      elif pp.endswith('.json'):
        sendx(self, 'application/json', Path(pp).read_text().encode())
      elif pp.endswith('.js'):
        sendx(self, 'text/javascript', Path(pp).read_text().encode())
      elif pp.endswith('.css'):
        sendx(self, 'text/css', Path(pp).read_text().encode())
      return True
  return False

def server(cmd, port=17173, static=None):
  if cmd is None or type(cmd) != list or len(cmd)==0:
    return
  if static is None: static = {}
  static['vygdb'] = os.path.join(BASEPATH, 'main')
  class VygdbHttpRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
      if self.path == '/':
        sendx(self, 'text/html', Path(os.path.join(BASEPATH, 'main', 'main.html')).read_text().encode())
      elif self.path == '/start_gdb':
        _restart(['gdb', '--silent', '-x', vygdbpath, '--args']+cmd)
        self.send_response(200)
        self.end_headers()
      else:
        for k,v in static.items():
          if newpath(self,self.path,k,v): return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
      if 'top' in static and self.path == '/top/vdbg_actions.json':
        try:
          x = self.rfile.read(int(self.headers["Content-Length"])).decode('utf-8')
          x = json.dumps(json.loads(x), sort_keys=True, indent=2)
          Path(os.path.join(static['top'], 'vdbg_actions.json')).write_text(x)
        except Exception as exc:
          print('fail',exc,flush=True)
      self.send_response(200)
      self.end_headers()

  print('Serving vygdb on http://localhost:{p}'.format(p=port),flush=True)
  TCPServer.allow_reuse_address = True
  with TCPServer(("", port), VygdbHttpRequestHandler) as httpd:
    httpd.serve_forever()
  
if __name__ == '__main__':
  server()