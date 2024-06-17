import argparse, collections, configparser, grp, pwd, hashlib, os, re, sys, zlib
from datetime import datetime
from fnmatch import fnmatch
from math import ceil

# Basic argparse initialization
arg_p = argparse.ArgumentParser(description="Content Tracker.")

arg_sub_p = arg_p.add_subparsers(title="Commands", dest="command")
arg_sub_p.required = True

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
    
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository: edit this file 'description' to name the repository.\n")
    
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")
    
    with open(repo_file(repo, "config"), "w") as f:
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

argsp = arg_sub_p.add_parser("init", help="Initialize a new, empty repository.")

argsp.add_argument("path", metavar="directory", nargs="?", default=".", help="Where to create the repository.")

def init_command(args):
    repo_create(args.path)
    print("Initialized empty Git repository in %s" % os.path.abspath(args.path))
    
def repo_find(path=".", required=True):
    path = os.path.realpath(path)
    
    # Check if path is a git directory
    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)
    
    # Check if path is a subdirectory of a git directory
    parent = os.path.realpath(os.path.join(path, ".."))
    
    if parent == path:
        # if parent==path, then path is root
        if required:
            raise Exception("No git directory.")
        else:
            return None
    
    return repo_find(parent, required)

class GitObject (object):
    def __init__(self, repo, data=None):
        self.repo = repo
        
        if data != None:
            self.deserialize(data)
        else:
            self.init()
        
    def init(self):
        pass
    
    def serialize(self):
        raise Exception("Unimplemented")
    
    def deserialize(self, data):
        raise Exception("Unimplemented")

# object_read function to read object from repository
def object_read(repo, sha):
    # path to object file in repository
    path = repo_file(repo, "objects", sha[0:2], sha[2:])
    
    if not os.path.isfile(path):
        raise Exception("Object file missing %s" % path)
    
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())
        
        # find the space in the raw data
        x = raw.find(b' ')
        fmt = raw[0:x]
        
        # find the null byte in the raw data
        y = raw.find(b'\x00', x)
        
        # size of the object is the string between the space and the null byte
        size = int(raw[x:y].decode("ascii"))
        
        # check if the size is equal to the length of the raw data minus the null byte
        if size != len(raw) - y - 1:
            raise Exception("Malformed object {0}: bad length".format(sha))
        
        # match the format of the object to the following cases
        match fmt:
            case b'commit'	: c=GitCommit
            case b'tree'	: c=GitTree
            case b'tag'     : c=GitTag
            case b'blob'	: c=GitBlob
            case _			: raise Exception("Unknown type %s!" % fmt)
        
        # return the object with the repository and the raw data
        return c(repo, raw[y+1:])

def object_write(obj, repo=None):
    data = obj.serialize()
    
    # result adds header to the data and compresses it
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    
    # sha is the hash of the result
    sha = hashlib.sha1(result).hexdigest()
    
    if repo:
        # if checks if the object exists in the repository
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(zlib.compress(result))
    return sha

class GitBlob(GitObject):
    fmt=b'blob'
    
    def serialize(self):
        return self.blobdata
    
    def deserialize(self, data):
        self.blobdata = data

argsp = arg_sub_p.add_parser("cat-file", help="Provide content of repository objects.")

argsp.add_argument("type", metavar="type", choices=["blob", "commit", "tag", "tree"], help="Specify the type.")

argsp.add_argument("object", metavar="object", help="The object to display.")

def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())

def object_find(repo, name, fmt=None, follow=True):
    return name

argsp = arg_sub_p.add_parser("hash-object", help="Compute object ID and optionally creates a blob from a file.")

argsp.add_argument("-t", metavar="type", dest="type", choices=["blob", "commit", "tag", "tree"], default="blob", help="Specify the type.")

argsp.add_argument("-w", dest="write", action="store_true", help="Write the object into the database.")

argsp.add_argument("path", help="Read object from <file>.")

def cmd_hash_object(args):
    if args.write:
        repo = repo_find()
    else: repo = None
    
    with open(args.path, "rb") as f:
        sha = object_hash(f, args.type.encode(), repo)
        print(sha)

def object_hash(data, fmt, repo=None):
    data = data.read()
    
    match fmt:
        case b'blob'	: obj = GitBlob(data)
        case b'tree'	: obj = GitTree(data)
        case b'commit'	: obj = GitCommit(data)
        case b'tag'	: obj = GitTag(data)
        case _			: raise Exception("Unknown type %s!" % fmt)

def kvlm_parse(raw, start=0, dct=None):
    if not dct:
        dct = collections.OrderedDict()
    
    # find the first space and newline in the raw data
    spc = raw.find(b' ', start)
    nl = raw.find(b'\n', start)

    # if there is no space or the newline is before the space then the key is None and the value is the raw data
    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start+1:]
        return dct
    
    # key is the data between the start and the space
    key = raw[start:spc]

    # find the end of the value by finding the next newline
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' '): break

    # value is the data between the space and the newline
    value = raw[spc+1:end].replace(b'\n ', b'\n')
    
    # if the key is in the dictionary, then the value is appended to the key, else the key is the value
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [ dct[key], value ]
    else:
        dct[key]=value

    # recursively call the function with the new start and dictionary
    return kvlm_parse(raw, start=end+1, dct=dct)

