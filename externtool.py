# Copyright (C) 2006  Stephen Ward

# GNU GPL v2.

"""
ExternalTool class

This is a base class for defining external tools, to extend and customize
Bazaar (bzr).
"""

import subprocess
import copy
from os.path import join, isfile
from os import pathsep, environ

from bzrlib import errors


class ExternalTool(object):
  """
  Base class for defining external tools.

  This class provides a few very general features: tool name, options,
  supported capabilities, a registration mechanism, and a run() method.
  
  The known tools are recorded in a nested dictionary, where the first
  level is keyed on tool kind ('diff', 'merge', etc.) and the second
  level is keyed on tool name ('kdiff3', 'meld', etc.).  The objects 
  stored in this structure are instances of the appropriate subclass,
  which are cloned by the 'find' method as needed.
  
  Supported capabilities can be recorded and queried using the 
  'supports' method.  Almost anything can be stored as a capability,
  but this mechanism is most often used for simple flags, e.g. 
  {'recursive': True}.
  """
  
  # Keep a dictionary of known tools {kind : {tool: exemplar_instance}}:
  known_tools = {}

  def __init__(self, name, *args, **kwargs):
    """
    Initialize an ExternalTool with the command and default options.
    """
    self.command = name
    self.options = ''
    self.capabilities = kwargs
    return

  def add_options(self, options):
    """
    Add more options to this instance of the tool.
    """
    if options:
      assert isinstance(options, basestring)
      self.options = self.options + ' ' + options
    return

  def supports(self, key, value=None):
    """
    Check (or record) if this tool supports a particular capability.
    """
    assert isinstance(key, basestring)
    if value is not None:
      self.capabilities[key] = value
      return value
    elif key in self.capabilities:
      return self.capabilities[key]
    else:
      return None

  def run(self):
    """
    Execute the command, return the result.
    """
    if self.options:
      opts = self.options.split()
    else:
      opts = []

    run_tool = [self.command] + opts
    return subprocess.call(run_tool)

  @staticmethod
  def register(kind, tool):
    """
    Register a known tool, using an exemplar of its class.

    This exemplar will be cloned to create a new instance on each tool
    invocation, so any options provided to the exemplar will be used
    for all other instances of this tool (as will the exemplar's class).

    If the same tool is registered more than once, the last one wins.
    """
    assert isinstance(tool, ExternalTool)
    assert tool.supports(kind)
    if kind not in ExternalTool.known_tools:
      ExternalTool.known_tools[kind] = {}
    ExternalTool.known_tools[kind][tool.command] = tool

    return tool

  @staticmethod
  def find(kind, name):
    """
    Find a known tool and create an instance of it. (Factory method)
    """
    tool = None
    if kind in ExternalTool.known_tools:
      if name in ExternalTool.known_tools[kind]:
        tool = copy.copy(ExternalTool.known_tools[kind][name])
        ExternalTool.check_path(tool.command)
    
    return tool

  @staticmethod
  def check_path(name):
    """
    Check if this tool is actually available on this system.
    """
    found = False
    exe_path = environ.get('PATH', '')
    for path in exe_path.split(pathsep):
      if path and isfile(join(path, name)):
        found = True
    if not found:
      raise errors.BzrError("Cannot find '%s' in %s" % (name, exe_path))

    return

  # End class ExternalTool

# The End.
