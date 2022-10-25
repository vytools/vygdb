'''
TODO: USe this for all STL https://gist.github.com/skyscribe/3978082
gdb --batch-silent -x thing_gdb_commands.py --args executablename arg1 arg2 arg3
https://gcc.gnu.org/ml/libstdc++/2009-02/msg00056.html

print([gdb.TYPE_CODE_PTR,  gdb.TYPE_CODE_ARRAY,     gdb.TYPE_CODE_STRUCT,  gdb.TYPE_CODE_UNION,
  gdb.TYPE_CODE_ENUM,      gdb.TYPE_CODE_FLAGS,     gdb.TYPE_CODE_FUNC,    gdb.TYPE_CODE_INT,
  gdb.TYPE_CODE_FLT,       gdb.TYPE_CODE_VOID,      gdb.TYPE_CODE_SET,     gdb.TYPE_CODE_RANGE,
  gdb.TYPE_CODE_STRING,    gdb.TYPE_CODE_BITSTRING, gdb.TYPE_CODE_ERROR,   gdb.TYPE_CODE_METHOD,
  gdb.TYPE_CODE_METHODPTR, gdb.TYPE_CODE_MEMBERPTR, gdb.TYPE_CODE_REF,     gdb.TYPE_CODE_CHAR,
  gdb.TYPE_CODE_BOOL,      gdb.TYPE_CODE_COMPLEX,   gdb.TYPE_CODE_TYPEDEF, gdb.TYPE_CODE_NAMESPACE,
  gdb.TYPE_CODE_DECFLOAT,  gdb.TYPE_CODE_INTERNAL_FUNCTION])

'''
import asyncio
import websockets
import re, json, math, sys, uuid
global STREAMER, VYGDB, LASTCMD, TOPIC_QUEUE, QUEUE
QUEUE = asyncio.Queue(maxsize=2000)
TOPIC_QUEUE = {}
STREAMER = None
LASTCMD = None
VYGDB = {'METHODS':{},'MARSHALS':{},'BREAKPOINTS':{},'DATA':{}}

try:
  import gdb
  class custom_breakpoint(gdb.Breakpoint):
    def __init__(self, source, action):
      gdb.Breakpoint.__init__(self, source)
      self.source = source
      self.set_action(action)

    def set_action(self,action):
      self.variables = action['variables'] if 'variables' in action else []
      self.topic = action['topic'] if 'topic' in action else None
      self.method = action['method'] if 'method' in action else None
      self.breakstop = action['stop'] if 'stop' in action else False
      self.action = action

    # def msgstop(self):
    #   send_to_vyclient({'topic':'output','message':'Waiting for client input'})

    def stop(self):

      def send(msg):
        reply = {'variables':msg}
        for x in self.action:
          if x not in ['breakpoint', 'variables']:
            reply[x] = self.action[x]
        return send_to_vyclient(reply)

      msg = extractvariables(self.variables)
      if msg is None:
        print('Error at' + self.source, flush=True)
        # self.msgstop()
        return True

      stop_ = gdb.parse_and_eval(self.breakstop) != False if type(self.breakstop) == str else self.breakstop
      if self.method is not None and self.method in VYGDB['METHODS']:
        try:
          stopb = VYGDB['METHODS'][self.method](msg, {
            'gdb':gdb,
            'marshal':marshal,
            'send':send,
            'data':VYGDB['DATA'],
            'self':self
          })
          if type(stopb) == bool:
            stop_ = stop_ or stopb
        except Exception as exc:
          print('vygdb.custom_breakpoint error: Problem running method ' + str(self.method) + ' at ' + self.source + '\n', exc,flush=True)
          # self.msgstop()
          return True

      if msg and self.topic is not None:
        if not send(msg):
          # self.msgstop()
          return True # Stop if message send failed
      
      if stop_:
        latest_position()
        # self.msgstop()
        return True
      else:
        return False

except Exception as exc:
  gdb = None

class ParseSourceException(Exception):
    pass

def find_type(orig, name):
  typ = orig.strip_typedefs()
  while True:
    # Strip cv-qualifiers.  PR 67440.
    search = '%s::%s' % (typ.unqualified(), name)
    try:
        return gdb.lookup_type(search)
    except RuntimeError:
        pass
    # The type was not found, so try the superclass.  We only need
    # to check the first superclass, so we don't bother with
    # anything fancier here.
    field = typ.fields()[0]
    if not field.is_base_class:
      raise ValueError("Cannot find type %s::%s" % (str(orig), name))
  typ = field.type

class _iterator:
  def __init__ (self, start, finish):
    self.item = start
    self.finish = finish
    self.count = 0

  def __iter__(self):
    return self

  def next(self):
    if self.item == self.finish:
      raise StopIteration
    count = self.count
    self.count = self.count + 1
    elt = self.item.dereference()
    self.item = self.item + 1
    return elt

def _vector(variable):
  first = variable['_M_impl']['_M_start']
  last = variable['_M_impl']['_M_finish']
  lngth = int(last-first)
  it = _iterator(first, last)
  x = []
  count = 0
  while count < lngth:
    try:
      x.append(marshal( it.next() ))
    except Exception as exc:
      print('vygdb._vector exception:',exc,flush=True)
      break
    count += 1
  return x

def _tuple(head):
  # https://gcc.gnu.org/ml/libstdc++/2009-10/msg00102.html
  nodes = head.type.fields () # should be length 1
  head = head.cast (nodes[0].type)
  x = []
  count = 0
  while head is not None:
    nodes = head.type.fields()  # should be length 2
    impl = head.cast (nodes[-1].type)  # Right node is the actual class contained in the tuple.
    head = None if len(nodes)<2 else head.cast (nodes[0].type) # Left node is the next recursion parent, set it as head.
    fields = impl.type.fields ()
    if len (fields) < 1 or fields[0].name != "_M_head_impl":
        pass # I dont know what to do here
    else:
        x.append(marshal(impl['_M_head_impl']))
    count += 1
  return x

def _struct(variable):
  fields = []
  for field in variable.type.fields():
    if not (field.artificial or field.name is None):
      fields.append(field.name)
  isstring = all([field in ['_M_dataplus','_M_string_length','npos'] for field in fields])
  if len(fields) == 0 or isstring:
    try:
      if isstring:
        l = variable['_M_string_length']
        x = str(variable['_M_dataplus']['_M_p'].string (length = l))
      else:
        x = str(variable)
    except Exception as exc:
      x = str(variable)
  else:
    x = {}
    for name in fields:
      x[name] = marshal(variable[name])
  return x

def marshal(variable):
  typ = variable.type
  if typ.code == gdb.TYPE_CODE_TYPEDEF:
    typ = typ.strip_typedefs()
  vtype = str(typ)
  x = None
  try:
    if typ.code in [gdb.TYPE_CODE_REF]:
      x = marshal(variable.referenced_value())
    elif typ.code in [gdb.TYPE_CODE_PTR]:
      x = marshal(variable.dereference())
    elif vtype.find("const std::shared_ptr") == 0 or vtype.find("std::shared_ptr") == 0:
      x = marshal(variable['_M_ptr'].referenced_value())
    elif typ.code == gdb.TYPE_CODE_VOID:
      x = None
    elif vtype.find("const std::vector") == 0 or vtype.find("std::vector") == 0 or vtype.find("const std::deque") == 0 or vtype.find("std::deque") == 0:
      x = _vector(variable)
    elif vtype.find("const std::tuple") == 0 or vtype.find("std::tuple") == 0:
      x = _tuple(variable)
    elif vtype.find("const std::function") == 0 or vtype.find("std::function") == 0:
      x = None
    elif vtype.find("const std::map") == 0 or vtype.find("std::map") == 0:
      x = _map(variable)
    elif vtype.find("const std::unordered_map") == 0 or vtype.find("std::unordered_map") == 0:
      x = _map(variable)
    elif vtype.find("const std::allocator") == 0 or vtype.find("std::allocator") == 0:
      x = _map(variable)
    elif typ.code == gdb.TYPE_CODE_FLT:
      x = float(variable)
      if math.isnan(x):
        x = None
    elif typ.code == gdb.TYPE_CODE_INT:
      x = int(variable)
    elif typ.code == gdb.TYPE_CODE_BOOL:
      x = bool(variable)
    elif typ.code in [gdb.TYPE_CODE_ENUM]:
      x = '"'+str(variable)+'"' # enums return as string not value
    elif vtype in VYGDB['MARSHALS']:
      x = VYGDB['MARSHALS'][vtype](variable, marshal, gdb)
    else:
      if vtype.endswith(']'):
        n = int(vtype.split('[',-1)[-1].strip(']'))
        x = [_struct(variable[i]) for i in range(n)]
      else:
        x = _struct(variable)
  except Exception as exc:
    print('vygdb.marshal Exception = ',exc)
    print('vtype = ',vtype)
    print('typ.code = ',typ.code)
    print('variable = ',variable,flush=True)
  return x

def extractvariables(variables):
  msg = {}
  for variablemap in variables:
    try:
      v = variables[variablemap]
      msg[variablemap] = marshal(gdb.parse_and_eval(v)) if type(v) == str else v
    except Exception as exc:
      print('vygdb.custom_breakpoint error: Could not access variable ' + variables[variablemap], exc,flush=True)
      return None
  return msg

def exit_handler (event):
  exitflag = None
  try:
    exitflag = marshal(gdb.parse_and_eval('$_exitcode'))
  except Exception as exc:
    pass
  if exitflag is None:
    exitflag = 1
  gdb.execute("quit "+str(exitflag))

def action_assignment(action):
  if 'active' not in action:
    action['active'] = False
  if 'source' in action:
    if 'breakpoint' in action:
      if not action['active']: # delete
        action['breakpoint'].delete()
        del action['breakpoint']
      else: # update
        action['breakpoint'].set_action({k:v for k,v in action.items() if k != 'breakpoint'})
    elif 'breakpoint' not in action and action['active']: # add
      action['breakpoint'] = custom_breakpoint(action['source'],action)
  else:
    print('vygdb_breakpoint:: ',action,'must have "source" ["name", "variables", "topic", and "method" are optional fields]')
  sys.stdout.flush()

def marshals_and_methods(textlist):
  global VYGDB
  for text in textlist:
    tempvygdb = {'MARSHALS':{},'METHODS':{}}
    exec(text, {}, tempvygdb)
    for typ in ['MARSHALS','METHODS']:
      for x in tempvygdb[typ]:
        print('Adding ',typ,x,flush=True)
        if x in VYGDB[typ]:
          raise ParseSourceException("Duplicate "+typ+" definition of "+typ+'"')
        VYGDB[typ][x] = tempvygdb[typ][x]

def parse_sources(replace_paths=[]):
  sources = gdb.execute("info sources",to_string=True)
  pattern1 = 'Source files for which symbols have been read in:'
  pattern2 = 'Source files for which symbols will be read in on demand:'
  p1s = sources.find(pattern1)
  p2s = sources.find(pattern2)
  vyscripts_filter_breakpoints = []
  parsed_breakpoints = {}
  if p1s >= 0 and p2s >=0 :
    symbols = sources[p1s+len(pattern1):p2s].strip().split(', ') + sources[p2s+len(pattern2):].strip().split(', ')
    for filename in symbols:
      for rpath in replace_paths:
        filename = filename.replace(rpath['old'],rpath['new'])

      delimiter = re.compile('(?s)<vdbg_bp(.*?)vdbg_bp>', re.MULTILINE|re.DOTALL)
      try:
        print('Trying to read vygdb symbols from "'+filename+'"',flush=True)
        with open(filename, 'r', encoding='utf-8') as file:
          string = file.read() #vyscripts += delimiter.findall(file.read())
          line = [m.end() for m in re.finditer('.*\n',string)]

        for m in re.finditer(delimiter, string):
          lineno = next(i for i in range(len(line)) if line[i]>m.start(1))
          mtch = m.group(1)
          try:
            cmd = json.loads(mtch)
            cmd['source'] = filename.split('/')[-1]+':'+str(lineno+1)
            if 'active' not in cmd:
              cmd['active'] = False # Always default to false
            duplicate = False
            for c in parsed_breakpoints.values():
              duplicate = cmd['source']==c['source']
              if duplicate:
                print('  vygdb.parse_sources: Warning: Duplicate breakpoint ignored (potentially in header file) {}'.format(cmd))
                break
            if not duplicate:
              parsed_breakpoints[uuid.uuid4().hex] = cmd
          except Exception as exc:
            vyscripts_filter_breakpoints.append(mtch)

      except Exception as exc:
        print('  vygdb.parse_sources: warning, failed reading of '+filename+':',exc,flush=True)
  print('Done reading sources',flush=True)
  return vyscripts_filter_breakpoints,parsed_breakpoints

def parse_gdb_command(cmd):
  global LASTCMD, VYGDB
  if cmd is None:
    return
  elif type(cmd) is not str:
    print('received in vygdb is not a string',cmd)
    cmd = None
  elif cmd.startswith('vb '):
    bp_update = json.loads(cmd.replace('vb ',''))
    if 'id' in bp_update and bp_update['id'] in VYGDB['BREAKPOINTS']:
      bp_current = VYGDB['BREAKPOINTS'][bp_update['id']]
      bp_current.update(bp_update)
      action_assignment(bp_current)
    cmd = None
  elif cmd.startswith('vtf '):
    fname = cmd.replace('vtf ','')
    with open(fname, 'r', encoding='utf-8') as cf:
      send_to_vyclient({'topic':'vdbg_file','filename':fname,'file':cf.read()})
    cmd = None
  elif cmd.startswith('v '):
    try:
      rslt = cmd + " = "+json.dumps(marshal(gdb.parse_and_eval(cmd[2:])))
    except Exception as exc:
      rslt = cmd + " = "+str(exc)
    print(rslt,flush=True)
    send_to_vyclient({'topic':'output','message':rslt})
    cmd = None
  elif cmd.startswith('vt '):
    try:
      msg = json.loads(cmd[3:])
      msg['variables'] = extractvariables(msg['variables'])
      if 'topic' in msg:
        send_to_vyclient(msg)
    except Exception as exc:
      print('The topic command',cmd[3:],'must be json formatted and should have "topic" and "variables" fields')
    sys.stdout.flush()
    cmd = None
  elif cmd.startswith('e '):
    try:
      eval(cmd[2:])
    except Exception as exc:
      print(exc)
    sys.stdout.flush()
    cmd = None

  if cmd is not None:
    try:
      cmd = LASTCMD if len(cmd)==0 and LASTCMD is not None else cmd
      if cmd.strip() == 'q': print('Quitting...')
      gdb.execute( cmd )
      sys.stdout.flush()
      LASTCMD = cmd
      latest_position()
    except Exception as exc:
      print('vygdb problem executing ',cmd,exc,flush=True)
      sys.exit(101)

def latest_position():
  currentfile = None
  try:
    # I'm sure there's a better way of getting linenumber and file from gdb class but I can't figure it out
    x = gdb.newest_frame().find_sal()
    if x is not None and x.is_valid() and x.symtab.is_valid():
      currentfile = x.symtab.filename
      send_to_vyclient({'topic':'vdbg_current','filename':currentfile,'line':x.line})
  except Exception as exc:
    print('vygdb latest_position error:',exc,flush=True)
  return currentfile

def first_response(data):
  global VYGDB, LASTCMD
  VYGDB['BREAKPOINTS'] = data['breakpoints'] if 'breakpoints' in data else {}
  vyscripts = data['breakscripts'] if 'breakscripts' in data else []
  marshals_and_methods(vyscripts)
  for action in VYGDB['BREAKPOINTS'].values():
    action_assignment(action)
  send_to_vyclient({'topic':'vdbg_actions_received'})
  gdb.execute("run")
  LASTCMD = None
  latest_position()

def send_to_vyclient(data):
  try:
    QUEUE.put_nowait(data)
    # TOPIC_QUEUE[data['topic']] = data
  except Exception as exc:
    print('vygdb failed to send data with topic {t}. {e}'.format(e=exc,t=data.get('topic',None)),flush=True)
    return False
  return True

def gdb_client(port=17172):
  replace_paths = []

  gdb.events.exited.connect(exit_handler)
  #gdb.execute("start") # Ensure shared libraries are loaded already (TODO, fix this? try-catch?)
  gdb.execute("set pagination off")
  gdb.execute("set python print-stack full")
  gdb.execute("set confirm off")
  vyscripts,breakpoints = parse_sources(replace_paths)

  async def streamer(websocket, path):
    global STREAMER
    STREAMER = websocket
    await websocket.send(json.dumps({
      'topic':'vdbg_actions',
      'breakpoints':breakpoints,
      'breakscripts':vyscripts
    }))

    print('waiting for first message from client',flush=True)
    async for message in websocket:
      data = json.loads(message)
      if data.get('topic',None) == 'vdbg_actions':
        first_response(data)
        break

    async for message in websocket:
      # if not message.startswith('vtf '):
      #   await STREAMER.send(json.dumps({'topic':'output','message':'vygdb processing ...'}))
      parse_gdb_command( json.loads(message).get('command',None) )
 
  async def sender():
    global STREAMER
    while True:
      msg = await QUEUE.get()
      await STREAMER.send(json.dumps(msg))

  host = "0.0.0.0"
  print('Creating vygdb websocket on ws://{h}:{p} ...'.format(h=host,p=port), flush=True)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(websockets.serve(streamer, host, port))
  loop.run_until_complete(sender())

if __name__ == '__main__':
  gdb_client()
