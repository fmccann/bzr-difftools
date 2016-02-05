# Copyright (C) 2006  Stephen Ward

# GNU GPL v2.

"""
Controller for running an external diff tool

This module provides the control logic for choosing what files to diff, and
which tool (and arguments) to use.  Most of the interactions with bzrlib
internals are isolated to this module.
"""

from bzrlib import (
    branch,
    errors,
    osutils,
    transport,
    workingtree,
    )

from difftool import (register_diff_tool, find_diff_tool, 
                      TreeDiffTool, ListDiffTool)
from tempdir import NamedTemporaryDir


class NoDifferencesFound(Exception):
  pass


class Controller:
  """
  Control how the diff tool is run (using what inputs, which tool, etc.).
  """

  def run(self, file_list=None, revision=None, using=None,
                         diff_options=None, prefix=None):
    """
    Run the external diff tool.
    """

    # Get an instance of this tool:
    assert using is not None
    tool = find_diff_tool(using)
    tool.add_options(diff_options)
    
    # Default to current working directory:
    if (not file_list or len(file_list) == 0):
      file_list = [ osutils.getcwd() ]

    # Pick the right comparison to perform:
    if revision:
      if (len(revision) == 1) or (revision[1].spec is None):
        result = compare_using(tool, file_list, revision[0])
      elif len(revision) == 2:
        result = compare_using(tool, file_list, revision[0], revision[1])
      else:
        raise errors.BzrCommandError(
            '--revision takes exactly one or two revision specifiers')
    else:
      # Just diff against the current base tree:
      result = compare_using(tool, file_list)

    return result

  # End class controller


# Functions:

def compare_using(tool, file_list=None, rev1=None, rev2=None):
  """
  Compare two branches or revisions using an external tool.
  
  Determine which revisions of the file to compare, extract them if
  necessary, and run the comparison.  Handle repository branches and
  non-local branches (see get_tree_files).
  """
  tmp_prefix = 'bzr_diff-'

  # Find the tree(s) and the files associated with each:
  (b1, work_tree1, file_ids1, remainder) = get_tree_files(file_list)
  trees_to_lock = [work_tree1]
  if (len(remainder) > 0):
    (b2, work_tree2, file_ids2, remainder) = get_tree_files(remainder)
    b2_in_working_tree = isinstance(work_tree2, workingtree.WorkingTree)
    trees_to_lock.append(work_tree2)
    if (len(remainder) > 0):
      raise errors.BzrCommandError("Cannot compare more than two branches")
    if rev1 or rev2:
      raise errors.BzrCommandError("Cannot specify -r with multiple branches")
  else:
    b2 = None
    b2_in_working_tree = False

  get_read_locks(trees_to_lock)
  try:

    kind = work_tree1.inventory.get_file_kind(file_ids1[0])
    in_subdir = (kind == 'directory' or kind == 'root_directory')
    in_working_tree = isinstance(work_tree1, workingtree.WorkingTree)
      
    # Decide which mode (tree or files) to use when writing to tmpdir:
    if (len(file_list) == 1 and not in_subdir):
      use_tree = False
    elif (b2 and not in_subdir):
      use_tree = False
    else:
      use_tree = True
  
    # Check if we need to adjust our tmpdir paths:
    if (len(file_list) == 1) or b2:
      if in_subdir:
        adjust_path = work_tree1.inventory.id2path(file_ids1[0])
      else:
        adjust_path = osutils.basename(file_list[0])
    else:
      adjust_path = ''
  
    cleanup = tool.supports('cleanup')

  finally:
    release_read_locks(trees_to_lock)

  try:
    # Use the 1st revision as the old version (basis_tree is the default):
    if rev1:
      old_tree = b1.repository.revision_tree(rev1.in_history(b1).rev_id)
      old_hint = "-rev%s" % rev1.in_history(b1).revno
    elif b2:
      old_tree = work_tree1
      old_hint = '-' + b1.nick
    else:
      old_tree = b1.basis_tree()
      old_hint = "-basis"

    get_read_locks(trees_to_lock)
    try:
      
      # Use the 2nd revision as the new version (working_tree is the default):
      if rev2:
        new_tree = b1.repository.revision_tree(rev2.in_history(b1).rev_id)
        delta = get_diffs_or_stop(old_tree, new_tree, file_ids1)
        new_hint = "-rev%s" % rev2.in_history(b1).revno
        new_tmp_dir = NamedTemporaryDir(tmp_prefix, new_hint, cleanup)
        new_tmp_dir.write_stuff(new_tree, file_ids1, use_tree)
        new_path = osutils.pathjoin(new_tmp_dir.path, adjust_path)
      elif b2_in_working_tree:
        # Files from two different branches, branch2 has a working tree:
        delta = get_diffs_or_stop(old_tree, work_tree2, file_ids2)
        if (len(file_list) == 1):
          new_path = work_tree2.id2abspath(file_ids2[0])
        else:
          new_path = work_tree2.abspath('')
      elif b2:
        # Files from two different branches, branch2 has no working tree:
        delta = get_diffs_or_stop(old_tree, work_tree2, file_ids2)
        new_hint = '-' + b2.nick
        new_tmp_dir = NamedTemporaryDir(tmp_prefix, new_hint, cleanup)
        new_tmp_dir.write_stuff(work_tree2, file_ids2, use_tree)
        new_path = osutils.pathjoin(new_tmp_dir.path, adjust_path)
      elif not in_working_tree:
        # Repository branch or remote branch, but only one revision:
        new_tree = b1.basis_tree()
        delta = get_diffs_or_stop(old_tree, new_tree, file_ids1)
        new_hint = "-basis"
        new_tmp_dir = NamedTemporaryDir(tmp_prefix, new_hint, cleanup)
        new_tmp_dir.write_stuff(new_tree, file_ids1, use_tree)
        new_path = osutils.pathjoin(new_tmp_dir.path, adjust_path)
      else:
        # Item(s) in working tree, just diff it in place:
        delta = get_diffs_or_stop(old_tree, work_tree1, file_ids1)
        if (len(file_list) == 1):
          new_path = work_tree1.id2abspath(file_ids1[0])
        else:
          new_path = work_tree1.abspath('')
  
      # No exceptions yet, so we really do need to extract the old version:
      if b2 and in_working_tree:
        if (len(file_list) == 1):
          old_path = work_tree1.id2abspath(file_ids1[0])
        else:
          old_path = work_tree1.abspath('')
      else:
        old_tmp_dir = NamedTemporaryDir(tmp_prefix, old_hint, cleanup)
        old_tmp_dir.write_stuff(old_tree, file_ids1, use_tree)
        old_path = osutils.pathjoin(old_tmp_dir.path, adjust_path)
    
    finally:
      # Release the locks before we start any interactive tools:
      release_read_locks(trees_to_lock)

    # Run the comparison:
    if (tool.supports('recursive')):
      result = tool.run(old_path, new_path)
    elif (len(file_list) == 1 and not in_subdir):
      result = tool.run(old_path, new_path)
    else:
      # Iterative diff:
      if adjust_path != '':
        path_list = [path.replace(adjust_path, '.', 1) 
            for (path, file_id, kind, text_mods, meta_mods) in delta.modified
            if text_mods]
      else:
        path_list = [path 
            for (path, file_id, kind, text_mods, meta_mods) in delta.modified
            if text_mods]
      result = tool.run(old_path, new_path, path_list)

    # Set the result, since external tools cannot be trusted to do so:
    result = 1

  except NoDifferencesFound:
    result = 0

  return result


def get_tree_files(file_list):
  """
  Get a tree, and the file_ids from that tree, from the inputs.
  
  This returns the tree (a working tree or basis tree), a list of the
  file_ids belonging to that tree, and a list of remaining files (that
  presumably belong to another tree).
  """

  file_id_list = []
  try:
    (tree, rel_path) = workingtree.WorkingTree.open_containing(file_list[0])
    branch1 = tree.branch
    base_path = osutils.normpath(tree.id2abspath(tree.get_root_id()))
  except errors.NoWorkingTree:
    (branch1, rel_path) = branch.Branch.open_containing(file_list[0])
    tree = branch1.basis_tree()
    base_path = osutils.normpath(branch1.base)
  except errors.NotLocalUrl:
    (branch1, rel_path) = branch.Branch.open_containing(file_list[0])
    tree = branch1.basis_tree()
    base_path = None

  tree.lock_read()
  try:

    i = 0
    for file_name in file_list:
      try:
        if i > 0:
          if base_path:
            rpath = osutils.relpath(base_path, file_name)
          else:
            (branch2, rpath) = branch.Branch.open_containing(file_name)
            if branch2.base != branch1.base:
              raise errors.PathNotChild(file_name, branch1.base)
        else:
          rpath = rel_path
        file_id = tree.inventory.path2id(rpath)
        if file_id:
          file_id_list.append(file_id)
        else:
          if (not isinstance(transport.get_transport(file_name),
                             transport.local.LocalTransport)):
            raise errors.PathNotChild(file_name, branch1.base)
          else:
            raise errors.NotVersionedError(file_name)
        i += 1
      except errors.PathNotChild:
        break
        
  finally:
    tree.unlock()

  return (branch1, tree, file_id_list, file_list[i:len(file_list)])


def get_diffs_or_stop(old_tree, new_tree, file_id_list):
  """
  Use Tree.changes_from() to check if there is work to do.
  
  This can return 'delta' even if no text modifications were found,
  since some tools (especially recursive tree diffs) can do something
  useful with additions/deletions/renames.
  """
  path_list = [new_tree.id2path(file_id) 
      for file_id in file_id_list 
      if new_tree.has_id(file_id)]

  delta = new_tree.changes_from(old_tree, specific_files=path_list)
  if ((len(delta.removed) + len(delta.added) + 
       len(delta.renamed) + len(delta.modified)) == 0):
    raise NoDifferencesFound
  
  return delta


def get_read_locks(tree_list):
  """
  Call tree.lock_read() on a list of trees.
  """
  for tree in tree_list:
    tree.lock_read()
    
  return


def release_read_locks(tree_list):
  """
  Call tree.unlock() on a list of trees.
  """
  for tree in tree_list:
    tree.unlock()
  
  return


# Initialize the module:

# Register known diff tools, and provide exemplars for later cloning:
register_diff_tool(TreeDiffTool('fldiff'))
register_diff_tool(ListDiffTool('gvim', diff_options='-f -d'))
register_diff_tool(ListDiffTool('gvimdiff', diff_options='-f'))
register_diff_tool(TreeDiffTool('kdiff3'))
register_diff_tool(TreeDiffTool('kompare'))
register_diff_tool(TreeDiffTool('meld'))
register_diff_tool(ListDiffTool('mgdiff'))
register_diff_tool(TreeDiffTool('opendiff', cleanup=False))
register_diff_tool(ListDiffTool('tkdiff'))
register_diff_tool(ListDiffTool('vim', diff_options='-d'))
register_diff_tool(ListDiffTool('vimdiff'))
register_diff_tool(TreeDiffTool('xxdiff', diff_options='--exclude=.bzr*'))

# The End.
