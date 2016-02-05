# Copyright (C) 2006  Stephen Ward

# GNU GPL v2.

"""
External diff tools plugin for Bazaar

This plugin overrides the default 'bzr diff' command to add a new option
'--using', which is used to specify an external diff tool to run in place
of the builtin implementation.  Usually, this will be some form of 
graphical diff tool.

If the '--using' option is not provided, the original builtin 'bzr diff'
behavior is used.

The default behavior for an external diff tool is encapsulated in the
DiffTool class (difftool.py).  This class can be extended in order to
customize the behavior for a particular tool.

There are at least two distinct use models for a diff tool: a recursive
tree diff (where the external tool is in control, once the revisions have
been extracted from 'bzr'), and an iterative diff (where 'bzr' is in
control).  Both are supported here.

If some '--using' options were handled internally by bzrlib (e.g. 
'--using patience-diff'), then these could be delegated to the superclass
safely.  So this option can potentially be used for both external diff
tools and alternate internal diff algorithms.

The 'cmd_diff' class, defined here, is a minimalist command extension; most
of the actual work is delegated to the Controller class instead.  The 
purpose of this separation is to minimize the startup overhead, by deferring
most of the 'import' processing until the command is actually executed.

Note that this extension is not truly a decorator for the 'diff' command,
because it does not always call the builtin 'diff' command.  This could 
be changed, if it became necessary to combine this extension with another 
'diff' decorator, by calling the builtin version in addition to the 
external tool (and by changing the 'decorate' option on register_command).
"""

from bzrlib import (
    builtins,
    commands,
    option,
    )

class cmd_diff(builtins.cmd_diff):
  """
  The '--using TOOL' option can be used to run an external diff tool.

  Some examples of supported diff tools include 'kdiff3', 'kompare', 
  'meld', 'vimdiff', and 'xxdiff'.  Other external diff tools are likely
  to work as well, as long as their basic arguments are in the same form
  as 'diff'.
  
  Most of these tools allow merging or editing, so they can be used to
  change the working copy, but this should be done carefully.  Changes 
  to temporary files will not be saved.
  
  External diff tools may need customization to filter out the '.bzr'
  control files.
  """

  # Add a new option to the builtin 'diff' command:
  takes_options = builtins.cmd_diff.takes_options + [
           option.Option('using', type=str, help='Use alternate diff tool.')]

  # Override the inherited run() and help() methods:

  def run(self, *args, **kwargs):
    """
    Choose which diff tool (external or builtin) to run.
    """
    from controller import Controller
    if 'using' in kwargs:
      # Run the specified external diff tool:
      return Controller().run(*args, **kwargs)
    else:
      # Run the builtin diff command normally:
      return super(cmd_diff, self).run(*args, **kwargs)


  def help(self):
    """
    Return help message for this class, including text from superclass.
    """
    from inspect import getdoc
    return getdoc(super(cmd_diff, self)) + '\n\n' + getdoc(self)

  # End class cmd_diff


# Initialize the plugin:
version_info = (0, 91, 0, 'final', 0)

# Register the new command provided by this plugin:
commands.register_command(cmd_diff, decorate=False)

# The End.
