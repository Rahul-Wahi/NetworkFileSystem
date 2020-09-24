import pickle, logging

from memoryfs import *


## This class implements an interactive shell to navigate the file system

class FSShell():

    def __init__(self, file):
        # cwd stored the inode of the current working directory
        # we start in the root directory
        self.cwd = 0
        self.FileObject = file

    # implements cd (change directory)
    def cd(self, dir):
        i = self.FileObject.Lookup(dir, self.cwd)
        if i == -1:
            print("Error: not found\n")
            return -1
        inobj = InodeNumber(self.FileObject.RawBlocks, i)
        inobj.InodeNumberToInode()
        if inobj.inode.type != INODE_TYPE_DIR:
            print("Error: not a directory\n")
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

                    print(filestring.decode())

            # Skip to the next block, back to while loop
            offset += BLOCK_SIZE

    # implements cat (print file contents)
    def cat(self, filename):
        file_inode_number = self.FileObject.Lookup(filename, self.cwd)
        bytearray = self.FileObject.Read(file_inode_number, 0, MAX_FILE_SIZE)

        if bytearray == -1:
            print("Error: Not a file\n")
            return -1
        print(bytearray.decode())

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
            else:
                print("command " + splitcmd[0] + "not valid.\n")


if __name__ == "__main__":
    # Initialize file for logging
    # Changer logging level to INFO to remove debugging messages
    logging.basicConfig(filename='memoryfs.log', filemode='w', level=logging.DEBUG)

    # Replace with your UUID, encoded as a byte array
    UUID = b'\x12\x34\x56\x78'

    # Initialize file system data
    logging.info('Initializing data structures...')
    RawBlocks = DiskBlocks()
    # Load blocks from dump file
    RawBlocks.InitializeBlocks(False, UUID)

    # Show file system information and contents of first few blocks
    RawBlocks.PrintFSInfo()
    RawBlocks.PrintBlocks("Initialized", 0, 16)

    # Initialize FileObject inode
    FileObject = FileName(RawBlocks)

    myshell = FSShell(FileObject)
    myshell.Interpreter()