from vygdb.server import server
from vygdb.gdb_client import gdb_client

__version__ = "0.0.1"

# kwargs={'cwd':'/home/nate/misc/other/SeeAndStop/build/src/GeometryCore/'},
# cmd = ['see_and_stop_vis_test', 'testobject.json', 'out.json']

def _commandline():
  import argparse, shlex
  parser = argparse.ArgumentParser(prog='vytools', description='tools for working with vy')
  parser.add_argument('--version','-v', action='store_true', help='Print version')
  parser.add_argument('--port', type=int, default=17173, help='server port number')
  parser.add_argument('--cmd', type=str, default='', help='program command and args')
  parser.add_argument('--static','-s', metavar='Folder=Path', action = 'append', required=False,
                      help=' Serve local folders to a browser for use with the vygdb rendering'
                            '(do not put spaces before or after the = sign). '
                            'If a path contains spaces, you should define '
                            'it with quotes: (e.g. top="/path to/my top folder".'
                            'In this example a file at "/path to/my top folder/handler.js".'
                            'Would be served to "/top/handler.js".')
  args = parser.parse_args()
  if args.version:
    print(__version__)
    return

  static = {}
  if 'static' in dir(args):
    for arg in args.static:
      if '=' not in arg:
        logging.error('A --static -s ({a}) failed to be in the form Folder=Path'.format(s=typ,a=arg))
        return
      else:
        (k,v) = arg.split('=',1)
        static[k] = v
  print(static)
  server(port=args.port, static=static, cmd=shlex.split(args.cmd))
