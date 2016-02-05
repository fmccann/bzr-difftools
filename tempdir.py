# Copyright (C) 2006  Stephen Ward

# GNU GPL v2.

"""
Named temporary directory that cleans up automatically
"""

import os

from bzrlib import (
    errors,
    export,
    osutils,
    )


class NamedTemporaryDir(object):
  """
  A named temporary directory that cleans itself up automatically.
  
  Similar to NamedTemporaryFile from tempfile, but does not rely on 
  keeping the file (directory) open.
  """

  def __init__(self, prefix='', suffix='', cleanup=True, readonly=True):
    """
    Create a temporary directory.
    """
    self.path = osutils.mkdtemp(prefix=prefix, suffix=suffix + '_tmp')
    self.readonly = readonly
    self.cleaned = (not cleanup)
    return
  
  def write_stuff(self, rev_tree, file_id_list, use_tree=False):
    """
    Write to either individual files, or a whole tree, based on flag.
    """
    if use_tree:
      self.write_tree(rev_tree, file_id_list)
    else:
      self.write_files(rev_tree, file_id_list)
    return

  def write_tree(self, rev_tree, file_id_list):
    """
    Write the whole revision tree contents to our temporary directory. 
    The directory will be removed when the ScratchArea is deleted.
    """
    osutils.delete_any(self.path)
    export.export(rev_tree, self.path, format='dir')
    self._make_readonly()

    return

  def write_files(self, rev_tree, file_id_list):
    """
    Find the desired revision of each file, write it to our temporary
    directory.  The directory will be removed when the ScratchArea is
    deleted.
    """
    for file_id in file_id_list:
      if rev_tree.has_id(file_id):
        base_name = osutils.basename(rev_tree.id2path(file_id))
        # write in binary mode, to avoid OS-specific translations:
        tmp_file = open(osutils.pathjoin(self.path, base_name), 'wb')
        osutils.pumpfile(rev_tree.get_file(file_id), tmp_file)
        tmp_file.close()

    self._make_readonly()

    return

  def cleanup(self):
    """
    Clean up a temporary directory and all its contents.
    """

    # As a safety precaution, make sure we didn't get a completely bogus path:
    if (not self.path.endswith('_tmp')):
      raise errors.BzrError("attempted to delete a non-tmp directory: %s" %
                            self.path)
    if (not self.cleaned):
      self.cleaned = True
      osutils.rmtree(self.path)
    return
    
  def __del__(self):
    """
    Automate filesystem cleanup when the scratch area is deleted.
    """
    self.cleanup()

  # Private Methods:
  
  def _make_readonly(self):
    """
    Make the contents of the temporary directory read-only.
    """
    if self.readonly:
      for (directory, subdirs, files) in os.walk(self.path):
        for file in files:
          osutils.make_readonly(osutils.pathjoin(directory, file))
    
    return

  # End class NamedTemporaryDir
  
# The End.
