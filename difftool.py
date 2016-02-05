# Copyright (C) 2006  Stephen Ward

# GNU GPL v2.

"""
DiffTool class and related functions

This class, and the associated functions for registering and finding
instances of a diff tool, can be used to customize the behavior of an
external diff tool.

It is not necessary to subclass DiffTool just to add default options;
this can already be done, simply by providing options when the tool is
registered:
  
   register_diff_tool(DiffTool('diff', diff_options='--exclude=.bzr*'))
  
These initial options will be inherited by all later instances of the
tool named 'diff', because they will all be clones of this instance.

Two subclasses are currently defined:  
   
   TreeDiffTool  (for recursive tree diffs like 'meld' and 'kompare')
   ListDiffTool  (for non-recursive tools like 'vimdiff' and 'mgdiff')

Additional keyword arguments can be provided at initialization, to
record details about the supported capabilities for this tool.  The 
following fields are currently recognized for DiffTool and subclasses:
  
   'recursive'
   'interactive'
   'diff'
   'cleanup'
   
These are generally set by default for particular DiffTool subclasses,
but can be changed for the parent class, like:
  
   register_diff_tool(DiffTool('vimdiff', recursive=False)

These capabilities can be queried (or overridden) using the 'supports'
method:
  
   foo = DiffTool('foodiff')
   if foo.supports('diff'):
     ...
   foo.supports('interactive', False)
   
More complicated customizations, such as adding new methods or 
overriding the behavior of the 'run' method, can be accomplished by
subclassing DiffTool.  Just register an instance of a custom subclass,
for example using ListDiffTool for tools that want to display the 
diffs one at a time:
  
   register_diff_tool(ListDiffTool('mgdiff'))
  
instead of an instance of DiffTool itself.
"""

import subprocess
from os.path import join
from tempfile import NamedTemporaryFile

from externtool import ExternalTool

  
class DiffTool(ExternalTool):
  """
  Class for representing external diff tools
  
  This class can be extended to customize the invocation of an external
  diff tool.  For simple customizations, such as specifying default
  arguments and options, see the register_diff_tool() function.
  """

  def __init__(self, name, diff_options='', **kwargs):
    """
    Initialize a DiffTool object with the command and default options.
    """
    super(DiffTool, self).__init__(name, **kwargs)
    self.supports('diff', True)
    # Set defaults, but only if the capability was not set via kwargs:
    if 'interactive' not in self.capabilities:
      self.supports('interactive', True)
    if 'cleanup' not in self.capabilities:
      self.supports('cleanup', True)
    self.options = diff_options
    return

  def run(self, old_path, new_path):
    """
    Execute the command, return the result.
    """
    if self.options:
      diff_opts = self.options.split()
    else:
      diff_opts = []

    # Redirect stderr to a temp log, so we are not bothered by the useless
    # clutter that some GUI apps spew when run from the shell.
    temp_log = NamedTemporaryFile(suffix='.log', prefix='bzr_' + self.command)

    run_tool = [self.command] + diff_opts + [old_path, new_path]
    result = subprocess.call(run_tool, stderr=temp_log)
    
    return result

  # End class DiffTool


class TreeDiffTool(DiffTool):
  """
  Subclass of DiffTool for tools that handle recursive tree diffs.

  Since recursion does not change the default behavior inherited from 
  the DiffTool class, this class just records the fact that recursion
  is supported.
  """

  def __init__(self, name, diff_options='', **kwargs):
    """
    Initialize a TreeDiffTool object with the command and default options.
    """
    super(TreeDiffTool, self).__init__(name, diff_options, **kwargs)
    self.supports('recursive', True)
    return

  # End class TreeDiffTool
  
  
class ListDiffTool(DiffTool):
  """
  Subclass of DiffTool for tools that work with lists, not recursive trees.
  
  Examples include VIM and mgdiff.  These tools also prefer to put the new
  path first, so the operands are swapped here.
  """

  def __init__(self, name, diff_options='', **kwargs):
    """
    Initialize a ListDiffTool object with the command and default options.
    """
    super(ListDiffTool, self).__init__(name, diff_options, **kwargs)
    self.supports('recursive', False)
    return
  
  def run(self, old_path, new_path, file_list=None):
    """
    Execute the command, return the result.
    """
    
    # Get confirmation before diffing the entire world:
    if self.supports('interactive'):
      if (file_list and len(file_list) > 1):
        print "There are %d files with differences to review" % len(file_list)
        val = raw_input('Do you wish to continue [Y/n]? ')
        if val.lower() in ('n', 'no'):
          return 1

    if self.options:
      diff_opts = self.options.split()
    else:
      diff_opts = []

    # Redirect stderr to a temp log, so we are not bothered by the useless
    # clutter that some GUI apps spew when run from the shell.
    temp_log = NamedTemporaryFile(suffix='.log', prefix='bzr_' + self.command)

    if (file_list and len(file_list) > 0):
      # Run the diff tool iteratively, just changing the paths on each call:
      for path in file_list:
        run_tool = [self.command] + diff_opts + [join(new_path, path),
            join(old_path, path)]
        result = subprocess.call(run_tool, stderr=temp_log)
    else:
      # Just one diff to run, no need for games with the input paths:
      run_tool = [self.command] + diff_opts + [new_path, old_path]
      result = subprocess.call(run_tool, stderr=temp_log)
    
    return result
  
  # End class ListDiffTool


def register_diff_tool(tool):
  """
  Register a known diff tool, using an exemplar of its class.
  
  This exemplar will be cloned to create a new instance on each tool
  invocation, so any options provided to the exemplar will be used
  for all other instances of this tool (as will the exemplar's class).
  
  If the same tool is registered more than once, the last one wins.
  """
  ExternalTool.register('diff', tool)
  return


def find_diff_tool(name):
  """
  Find or create an instance of this diff tool. (DiffTool Factory)
  
  By default, create a generic TreeDiffTool, but do not register it; 
  options added to this instance should not be shared with other
  instances.
  """
  tool = ExternalTool.find('diff', name)
  if not tool:
    tool = TreeDiffTool(name)
    ExternalTool.check_path(name)

  return tool

# The End.