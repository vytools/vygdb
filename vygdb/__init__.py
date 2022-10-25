import vygdb.server

__version__ = "2.0.5"

def _commandline():
  import argparse, shlex, os, logging
  parser = argparse.ArgumentParser(prog='vytools', description='tools for working with vy')
  parser.add_argument('--version','-v', action='store_true', help='Print version')
  parser.add_argument('--port', type=int, default=17173, help='server port number')
  parser.add_argument('--cmd', type=str, default='', help='program command and args')
  parser.add_argument('--static','-s', metavar='Folder=Path', action = 'append', required=False,
                      help=' Serve local folders to a browser for use with the vygdb rendering'
                            '(do not put spaces before or after the = sign). If a path contains'
                            ' spaces, you should define '
                            'it with quotes: (e.g. top="/path to/my top folder".'
                            'In this example a file at "/path to/my top folder/handler.js".'
                            'Would be served to "/top/handler.js".')
  args = parser.parse_args()
  if args.version:
    print(__version__)
    return

  static = {}
  if 'static' in dir(args) and args.static:
    for arg in args.static:
      if '=' not in arg:
        logging.error('A (--static -s) directory "{}" failed to be in the form Folder=Path'.format(arg))
        return
      else:
        (k,v) = arg.split('=',1)
        if not os.path.isdir(v):
          logging.error('"{}" is not a valid directory'.format(v))
          return
        static[k] = v
  server.server(shlex.split(args.cmd), port=args.port, static=static)

if __name__ == '__main__':
  _commandline()