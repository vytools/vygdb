import os, logging, threading, subprocess
from sanic import Sanic, response
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

def server(port=17173, static=None, cmd=None):
  if cmd is None:
    return
  
  cmd = ['gdb', '--silent', '-x', vygdbpath, '--args']+cmd
  _restart(cmd)

  app = Sanic(__name__)
  if static is not None:
    for k,v in static.items(): app.static(k, v)
  app.static('/', os.path.join(BASEPATH, 'main', 'main.html'))
  app.static('/vygdb', os.path.join(BASEPATH, 'main'))

  @app.post('/start_gdb')
  async def _app_startgdb(request):
    _restart(cmd)
    return response.json({})

  if static is None:
    @app.get('/top/handler.js')
    async def _app_fakehandler(request):
      return response.text('''export function initializer(x){};
        export function handler(x,y){}''', content_type='text/javascript')

  try:
    app.run(host="0.0.0.0", port=port, debug=False, access_log=False)
    print('Serving vygdb on http://localhost:{p}'.format(p=port),flush=True)
  except KeyboardInterrupt:
    print("Received exit, exiting.",flush=True)
  
if __name__ == '__main__':
  server()