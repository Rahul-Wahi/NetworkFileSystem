import pickle, logging

from memoryfs_client import *


## This class implements an interactive shell to navigate the file system

class FSShell():

    def __init__(self, file):
        # cwd stored the inode of the current working directory
        # we start in the root directory
        self.cwd = 0
        self.FileObject = file
        self.FileObject.InitRootInode()

    # implements cd (change directory)
    def cd(self, dir):
        i = self.FileObject.GeneralPathToInodeNumber(dir, self.cwd)
        if i == -1:
            print("cd: Error: " + dir + " not found\n")
            return -1
        inobj = InodeNumber(self.FileObject.RawBlocks, i)
        inobj.InodeNumberToInode()
        if inobj.inode.type != INODE_TYPE_DIR:
            print("cd: Error: " + dir + "not a directory\n")
            return -1
        self.cwd = i

    # implements ls (lists files in directory)
    def ls(self):
        # your code here
        inode_number = InodeNumber(self.FileObject.RawBlocks, self.cwd)
        inode_number.InodeNumberToInode()
        offset = 0
        scanned = 0

        # Iterate over all data blocks indexed by directory inode, until we reach inode's size
        while offset < inode_number.inode.size:

            # Retrieve directory data block given current offset
            b = inode_number.InodeNumberToBlock(offset)

            # A directory data block has multiple (filename,inode) entries
            # Iterate over file entries to search for matches
            for i in range(0, FILE_ENTRIES_PER_DATA_BLOCK):

                # don't search beyond file size
                if inode_number.inode.size > scanned:
                    scanned += FILE_NAME_DIRENTRY_SIZE

                    # Extract padded MAX_FILENAME string as a bytearray from data block for comparison
                    filestring = self.FileObject.HelperGetFilenameString(b, i)
                    file_inodenumber = self.FileObject.HelperGetFilenameInodeNumber(b, i)
                    file_inodeobj = InodeNumber(self.FileObject.RawBlocks, file_inodenumber)
                    file_inodeobj.InodeNumberToInode()
                    if file_inodeobj.inode.type == INODE_TYPE_DIR:
                        print("[" + str(file_inodeobj.inode.refcnt) + "]:" + filestring.decode() + "/")
                    else:
                        print("[" + str(file_inodeobj.inode.refcnt) + "]:" + filestring.decode())

            # Skip to the next block, back to while loop
            offset += BLOCK_SIZE

    # implements cat (print file contents)
    def cat(self, filename):
        filename = self.stripSeperator(filename)
        file_inode_number = self.FileObject.Lookup(filename, self.cwd)
        bytearray = self.FileObject.Read(file_inode_number, 0, MAX_FILE_SIZE)

        if bytearray == -1:
            print("cat: Error: '" + filename + "' Not a file\n")
            return -1
        print(bytearray.decode())

    # implement ln (creates a hard link of target with name 'linkname')
    def ln(self, target, linkname):
        self.FileObject.ACQUIRE()
        self.FileObject.Link(target, linkname, self.cwd)
        self.FileObject.RELEASE()

    # implement mkdir (create new directory)
    def mkdir(self, dirname):
        dirname = self.stripSeperator(dirname)

        if len(dirname) > MAX_FILENAME:
            print("mkdir: cannot create directory: '" + dirname + "' file name exceeds maximum name size")
            return -1

        self.FileObject.ACQUIRE()
        # Ensure it's not a duplicate - if Lookup returns anything other than -1
        if self.FileObject.Lookup(dirname, self.cwd) != -1:
            print("mkdir: cannot create directory '" + dirname + "': already exists")
            return -1

        # Find if there is an available inode
        inode_position = self.FileObject.FindAvailableInode()
        if inode_position == -1:
            print("mkdir: cannot create directory: no free inode available")
            return -1

        # Find available slot in directory data block
        fileentry_position = self.FileObject.FindAvailableFileEntry(self.cwd)
        if fileentry_position == -1:
            print("mkdir: cannot create directory: no entry available for another object")
            return -1
        self.FileObject.Create(self.cwd, dirname, INODE_TYPE_DIR)
        self.FileObject.RELEASE()

    # implement create (create new file)
    def create(self, filename):

        filename = self.stripSeperator(filename)

        if len(filename) > MAX_FILENAME:
            print("create: cannot create file: '" + filename + "' file name exceeds maximum name size")
            return -1

        self.FileObject.ACQUIRE()
        # Ensure it's not a duplicate - if Lookup returns anything other than -1
        if self.FileObject.Lookup(filename, self.cwd) != -1:
            print("create: cannot create file '" + filename + "': already exists")
            return -1

        # Find if there is an available inode
        inode_position = self.FileObject.FindAvailableInode()
        if inode_position == -1:
            print("create: cannot create file: no free inode available")
            return -1

        # Find available slot in directory data block
        fileentry_position = self.FileObject.FindAvailableFileEntry(self.cwd)
        if fileentry_position == -1:
            print("create: cannot create file: no entry available for another object")
            return -1

        self.FileObject.Create(self.cwd, filename, INODE_TYPE_FILE)
        self.FileObject.RELEASE()

    # implement append (append string to the end of existing file)
    def append(self, filename, data):
        self.FileObject.ACQUIRE()
        filename = self.stripSeperator(filename)
        file_inode_number = self.FileObject.Lookup(filename, self.cwd)

        if file_inode_number == -1:
            print("append: Error: " + filename + " does not exist")
            return -1

        file_inode = InodeNumber(self.FileObject.RawBlocks, file_inode_number)
        file_inode.InodeNumberToInode()

        if file_inode.inode.type != INODE_TYPE_FILE:
            print("append: Error: " + filename + " not a file")
            return -1


        offset = file_inode.inode.size

        data_bytearray = bytes(data, 'utf-8')

        bytes_written = self.FileObject.Write(file_inode_number, offset, data_bytearray)
        self.FileObject.RELEASE()
        if bytes_written == -1:
            print("append: can not append: space not available\n")
            return -1

    #remove './' from start and '/' from end of the name
    def stripSeperator(self, name):
        if name[0] == '.' and name[1] == '/':
            name = name[2:]

        return name

    def Interpreter(self):
        while (True):
            command = input("[cwd=" + str(self.cwd) + "]:")
            splitcmd = command.split()
            if splitcmd[0] == "cd":
                if len(splitcmd) != 2:
                    print("Error: cd requires one argument")
                else:
                    self.cd(splitcmd[1])
            elif splitcmd[0] == "cat":
                if len(splitcmd) != 2:
                    print("Error: cat requires one argument")
                else:
                    self.cat(splitcmd[1])
            elif splitcmd[0] == "ls":
                self.ls()
            elif splitcmd[0] == "exit":
                return
            elif splitcmd[0] == "ln":
                if len(splitcmd) != 3:
                    print("Error: ln requires two arguments")
                else:
                    self.ln(splitcmd[1], splitcmd[2])
            elif splitcmd[0] == "mkdir":
                if len(splitcmd) != 2:
                    print("Error: mkdir requires one argument")
                else:
                    self.mkdir(splitcmd[1])
            elif splitcmd[0] == "create":
                if len(splitcmd) != 2:
                    print("Error: create requires one argument")
                else:
                    self.create(splitcmd[1])
            elif splitcmd[0] == "append":
                if len(splitcmd) != 3:
                    print("Error: create requires two arguments")
                else:
                    self.append(splitcmd[1], splitcmd[2])
            else:
                print("command " + splitcmd[0] + " not valid.\n")


if __name__ == "__main__":
    # Initialize file for logging
    # Changer logging level to INFO to remove debugging messages
    logging.basicConfig(filename='memoryfs.log', filemode='w', level=logging.DEBUG)

    # Replace with your UUID, encoded as a byte array
    UUID = b'\x12\x34\x56\x78'
    server_url = 'http://localhost:8000'
    # Initialize file system data
    logging.info('Initializing data structures...')
    RawBlocks = DiskBlocks(server_url)
    # Load blocks from dump file
    RawBlocks.InitializeBlocks(True, UUID)
    #
    # # Show file system information and contents of first few blocks
    # RawBlocks.PrintFSInfo()
    # RawBlocks.PrintBlocks("Initialized", 0, 16)

    # Initialize FileObject inode
    FileObject = FileName(RawBlocks)

    myshell = FSShell(FileObject)
    myshell.Interpreter()