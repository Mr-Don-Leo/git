import argparse, collections, configparser, grp, pwd, hashlib, os, re, sys, zlib
from datetime import datetime
from fnmatch import fnmatch
from math import ceil

# Basic argparse initialization
arg_p = argparse.ArgumentParser(description="Content Tracker.")

arg_sub_p = arg_p.add_subparsers(title="Commands", dest="command")
arg_sub_p.required = True

argsp = arg_p.add_parser("init", help="Initialize a new, empty repository.")

def main(argv=sys.argv[1:]):
    args = arg_p.parse_args(argv)
	# Case match for commands, if argument passed that matches a command, function executed. 
    match args.command:
        case "add"		: add_command(args)
        case "init"		: init_command(args)
        case _			: print("Invalid Command.'")
        
class GitRepository (object):
    worktree = None
    gitdir = None
    config = None
    
    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")
        
        if not (force or os.path.isdir(self.gitdir)):
            raise Exception("Not a git repository %s" % path)
        
        self.config = configparser.ConfigParser()
        config_file = repo_file(self, "config")
        
        if config_file and os.path.exists(config_file):
            self.config.read([config_file])
        elif not force:
            raise Exception("Config File missing.")
        
        if not force:
            vers = int(self.config.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception("Unsupported repositoryformatversion %s" % vers)

def repo_path(repo, *path):
    return os.path.join(repo.gitdir, *path)

def repo_file(repo, *path, mkdir=False):
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
    path = repo_path(repo, *path)
    
    if os.path.exists(path):
        if (os.path.isdir(path)):
            return path
        else:
            raise Exception("Not a  directory %s" % path)
    
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None

def repo_create(path):
    repo = GitRepository(path, True)
    
    # check if exists or not, or if empty
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception ("%s is not a directory!" % path)
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception("%s is not empty!" % path)
    else:
        os.makedirs(repo.worktree)
    
    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)
    
    with open(repo_file(repo, "description"), w) as f:
        f.write("Unnamed repository: edit this file 'description' to name the repository.\n")
    
    with open(repo_file(repo, "HEAD"), w) as f:
        f.write("ref: refs/heads/master\n")
    
    with open(repo_file(repo, "config"), w) as f:
        config = repo_default_config()
        config.write(f)
    
    return repo

def repo_default_config():
    ret = configparser.ConfigParser()
    
    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")
    
    return ret


    
    