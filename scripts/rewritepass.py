#!/usr/bin/python
import os
import re
import sys

if len(sys.argv) != 3 and len(sys.argv) != 4:
  print("Use: %s <PassRegistry.def path> <passes> [run-tests]" % sys.argv[0])
  exit(1)

passregpath = sys.argv[1]

def wrap_str(arg, lst):
  for e in lst:
    arg = "%s(%s)" % (e, arg)
  return arg

def wrap(args):
  passes = args.split(',')

  pass_types = {
    "module"   : [],
    "cgscc"    : [],
    "function" : [],
    "loop"     : ["function"]
  }

  firstpass = None
  type = None

  skip = ['verify', 'invalidate<all>']
  for p in passes:
    if not any(p.startswith(s) for s in skip):
      firstpass = p
      break

  # decorated already: function(foo)
  for ty,lst in pass_types.items():
    if firstpass.startswith(ty + '('):
      return wrap_str(args, lst)

  override = {
    # pass -> (type, prepend-type?)
    'devirt<' : ('cgscc', True),
    'loop-mssa' : ('loop', False),
  }
  for arg,(ty,prepend) in override.items():
    if firstpass.startswith(arg):
      return wrap_str(args, ([ty] if prepend else []) + pass_types[ty])

  # strip e.g. require<foo> -> foo
  strip = [
    r'require<([^>]+)>',
    r'repeat<\d+>\(([^)]+)\)',
    r'invalidate<([^>]+)>',
    r'<[^>]+>()'
  ]
  for s in strip:
    firstpass = re.sub(s, '\\1', firstpass)

  # check LLVM's PassRegistry.def file
  txt = open(passregpath, 'r').read()
  p = re.escape(firstpass)
  m = re.search(r'^([A-Z_]+)_(?:PASS|ANALYSIS)[A-Z_]*\("' + p, txt, re.MULTILINE)
  if m is None:
    return wrap_str(args, ['module'])

  type = {
    'CGSCC'          : 'cgscc',
    'FUNCTION'       : 'function',
    'FUNCTION_ALIAS' : 'function',
    'LOOP'           : 'loop',
    'MODULE'         : 'module',
    'MODULE_ALIAS'   : 'module',
  }[m.group(1)]
  return wrap_str(args, [type] + pass_types[type])

def run_opt(passes):
  error = os.popen('echo "" | opt -passes="%s" -disable-output 2>&1' %
                    passes).close()
  return error is None

if len(sys.argv) == 3:
  print(wrap(sys.argv[2].strip("'\"")))
else:
  tests = [
    ('sroa', 'function(sroa)'),
    ('simplify-cfg', 'function(simplify-cfg)'),
    ('licm', 'function(loop(licm))'),
    ('argpromotion', 'cgscc(argpromotion)'),
    ('loop-extract', 'module(loop-extract)'),
    ('unswitch<nontrivial>', 'function(loop(unswitch<nontrivial>))'),
    ('sroa,verify', 'function(sroa,verify)'),
    ('verify,sroa', 'function(verify,sroa)'),
    ('loop-mssa(loop-instsimplify)', 'function(loop-mssa(loop-instsimplify))'),
    ('require<basic-aa>,sroa', 'function(require<basic-aa>,sroa)'),
    ('cgscc(repeat<2>(inline,function(dce)))', 'cgscc(repeat<2>(inline,function(dce)))'),
    ('repeat<2>(sroa)', 'function(repeat<2>(sroa))'),
    ('cgscc(devirt<4>(inline))', 'cgscc(devirt<4>(inline))'),
    ('devirt<1>(inline,function(gvn))', 'cgscc(devirt<1>(inline,function(gvn)))'),
    ('invalidate<domtree>,early-cse-memssa', 'function(invalidate<domtree>,early-cse-memssa)'),
    ('default<O2>', 'module(default<O2>)')
  ]

  for i,o in tests:
    if wrap(i) != o:
      print('FAIL:', i)
      print('Got:', wrap(i))
      print('Expected:', o)
      print()
    elif not run_opt(i):
      print('FAIL running input:', i)
    elif not run_opt(o + ',globalopt'):
      print('FAIL running output:', o)
    else:
      print('PASS:', i)