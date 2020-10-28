from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import xmlrpc.client
import base64
import pickle, logging
kv = {}

##### File system constants

# Core parameters
# Total number of blocks in raw storage
TOTAL_NUM_BLOCKS = 256
# Block size (in Bytes)
BLOCK_SIZE = 128
# Maximum number of inodes
MAX_NUM_INODES = 16
# Size of an inode (in Bytes)
INODE_SIZE = 16
# Maximum file name (in characters)
MAX_FILENAME = 12
# Number of Bytes to store an inode number in directory entry
INODE_NUMBER_DIRENTRY_SIZE = 4

# Derived parameters
# Number of inodes that fit in a block
INODES_PER_BLOCK = BLOCK_SIZE // INODE_SIZE

# To be consistent with book, block 0 is root block, 1 superblock
# Bitmap of free blocks starts at offset 2
FREEBITMAP_BLOCK_OFFSET = 2

# Number of blocks needed for free bitmap
# For simplicity, we assume each entry in the bitmap is a Byte in length
# This allows us to avoid bit-wise operations
FREEBITMAP_NUM_BLOCKS = TOTAL_NUM_BLOCKS // BLOCK_SIZE

# inode table starts at offset 2 + FREEBITMAP_NUM_BLOCKS
INODE_BLOCK_OFFSET = 2 + FREEBITMAP_NUM_BLOCKS

# inode table size
INODE_NUM_BLOCKS = (MAX_NUM_INODES * INODE_SIZE) // BLOCK_SIZE

# maximum number of blocks indexed by inode
# This implementation hardcodes:
#   4 bytes for size
#   2 bytes for type
#   2 bytes for refcnt
#   4 bytes per block number index
# In total, 4+2+2=8 bytes are used for size+type+refcnt, remaining bytes for block numbers
MAX_INODE_BLOCK_NUMBERS = (INODE_SIZE - 8) // 4

# maximum size of a file
# maximum number of entries in an inode's block_numbers[], times block size
MAX_FILE_SIZE = MAX_INODE_BLOCK_NUMBERS * BLOCK_SIZE

# Data blocks start at INODE_BLOCK_OFFSET + INODE_NUM_BLOCKS
DATA_BLOCKS_OFFSET = INODE_BLOCK_OFFSET + INODE_NUM_BLOCKS

# Number of data blocks
DATA_NUM_BLOCKS = TOTAL_NUM_BLOCKS - DATA_BLOCKS_OFFSET

# Size of a directory entry: file name plus inode size
FILE_NAME_DIRENTRY_SIZE = MAX_FILENAME + INODE_NUMBER_DIRENTRY_SIZE

# Number of filename+inode entries that can be stored in a single block
FILE_ENTRIES_PER_DATA_BLOCK = BLOCK_SIZE // FILE_NAME_DIRENTRY_SIZE

# Supported inode types
INODE_TYPE_INVALID = 0
INODE_TYPE_FILE = 1
INODE_TYPE_DIR = 2
INODE_TYPE_SYM = 3

#### BLOCK LAYER

class DiskBlocks():
    def __init__(self):
        # This class stores the raw block array
        self.block = []
        # Initialize raw blocks
        for i in range(0, TOTAL_NUM_BLOCKS):
            putdata = bytearray(BLOCK_SIZE)
            self.block.insert(i, putdata)

    ## Put: interface to write a raw block of data to the block indexed by block number
    ## Blocks are padded with zeroes up to BLOCK_SIZE

    def Put(self, block_number, block_data):
        if isinstance(block_data, xmlrpc.client.Binary):
            block_data = block_data.data

        logging.debug(
            'Put: block number ' + str(block_number) + ' len ' + str(len(block_data)) + '\n' + str(
                block_data.hex()))
        if len(block_data) > BLOCK_SIZE:
            logging.error('Put: Block larger than BLOCK_SIZE: ' + str(len(block_data)))
            quit()

        if block_number in range(0, TOTAL_NUM_BLOCKS):
            # ljust does the padding with zeros
            putdata = bytearray(block_data.ljust(BLOCK_SIZE, b'\x00'))
            # Write block
            self.block[block_number] = putdata
            return 0
        else:
            logging.error('Put: Block out of range: ' + str(block_number))
            quit()

    ## Get: interface to read a raw block of data from block indexed by block number
    ## Equivalent to the textbook's BLOCK_NUMBER_TO_BLOCK(b)

    def Get(self, block_number):
        logging.debug('Get: ' + str(block_number))
        if block_number in range(0, TOTAL_NUM_BLOCKS):
            # logging.debug ('\n' + str((self.block[block_number]).hex()))
            return self.block[block_number]

        logging.error('Get: Block number larger than TOTAL_NUM_BLOCKS: ' + str(block_number))
        quit()

    ## Serializes and saves block[] data structure to a disk file
    def DumpToDisk(self, prefix):
        filename = str(prefix.hex()) + "_BS_" + str(BLOCK_SIZE) + "_NB_" + str(TOTAL_NUM_BLOCKS) + "_IS_" + str(
            INODE_SIZE) + "_MI_" + str(MAX_NUM_INODES) + ".dump"
        logging.info("Dumping pickled blocks to file " + filename)
        file = open(filename, 'wb')
        pickle.dump(self.block, file)
        file.close()

    ## Loads block[] data structure from a disk file

    def LoadFromDisk(self, prefix):
        filename = str(prefix.hex()) + "_BS_" + str(BLOCK_SIZE) + "_NB_" + str(TOTAL_NUM_BLOCKS) + "_IS_" + str(
            INODE_SIZE) + "_MI_" + str(MAX_NUM_INODES) + ".dump"
        logging.info("Reading blocks from pickled file " + filename)
        file = open(filename, 'rb')
        block = pickle.load(file)
        for i in range(0, TOTAL_NUM_BLOCKS):
            self.Put(i, block[i])
        file.close()

    ## Initialize blocks, either from a clean slate (cleanslate == True), or from a pickled dump file with prefix

    def InitializeBlocks(self, cleanslate, prefix):
        if cleanslate:
            # Block 0: No real boot code here, just write the given prefix
            self.Put(0, prefix)

            # Block 1: Superblock contains basic file system constants
            # First, we write it as a list
            superblock = [TOTAL_NUM_BLOCKS, BLOCK_SIZE, MAX_NUM_INODES, INODE_SIZE]
            # Now we serialize it into a byte array
            self.Put(1, pickle.dumps(superblock))

            # Blocks 2-TOTAL_NUM_BLOCKS are initialized with zeroes
            #   Free block bitmap: All blocks start free, so safe to initialize with zeroes
            #   Inode table: zero indicates an invalid inode, so also safe to initialize with zeroes
            #   Data blocks: safe to init with zeroes
            zeroblock = bytearray(BLOCK_SIZE)
            for i in range(FREEBITMAP_BLOCK_OFFSET, TOTAL_NUM_BLOCKS):
                self.Put(i, zeroblock)
        else:
            self.LoadFromDisk(prefix)
            return 1

    ## Prints out file system information

    def PrintFSInfo(self):
        logging.info('#### File system information:')
        logging.info('Number of blocks          : ' + str(TOTAL_NUM_BLOCKS))
        logging.info('Block size (Bytes)        : ' + str(BLOCK_SIZE))
        logging.info('Number of inodes          : ' + str(MAX_NUM_INODES))
        logging.info('inode size (Bytes)        : ' + str(INODE_SIZE))
        logging.info('inodes per block          : ' + str(INODES_PER_BLOCK))
        logging.info('Free bitmap offset        : ' + str(FREEBITMAP_BLOCK_OFFSET))
        logging.info('Free bitmap size (blocks) : ' + str(FREEBITMAP_NUM_BLOCKS))
        logging.info('Inode table offset        : ' + str(INODE_BLOCK_OFFSET))
        logging.info('Inode table size (blocks) : ' + str(INODE_NUM_BLOCKS))
        logging.info('Max blocks per file       : ' + str(MAX_INODE_BLOCK_NUMBERS))
        logging.info('Data blocks offset        : ' + str(DATA_BLOCKS_OFFSET))
        logging.info('Data block size (blocks)  : ' + str(DATA_NUM_BLOCKS))
        logging.info('Raw block layer layout: (B: boot, S: superblock, F: free bitmap, I: inode, D: data')
        Layout = "BS"
        Id = "01"
        IdCount = 2
        for i in range(0, FREEBITMAP_NUM_BLOCKS):
            Layout += "F"
            Id += str(IdCount)
            IdCount = (IdCount + 1) % 10
        for i in range(0, INODE_NUM_BLOCKS):
            Layout += "I"
            Id += str(IdCount)
            IdCount = (IdCount + 1) % 10
        for i in range(0, DATA_NUM_BLOCKS):
            Layout += "D"
            Id += str(IdCount)
            IdCount = (IdCount + 1) % 10
        logging.info(Id)
        logging.info(Layout)

    ## Prints to screen block contents, from min to max

    def PrintBlocks(self, tag, min, max):
        logging.info('#### Raw disk blocks: ' + tag)
        for i in range(min, max):
            logging.info('Block [' + str(i) + '] : ' + str((self.Get(i)).hex()))


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)


# Create server
with SimpleXMLRPCServer(('localhost', 8000),
                        requestHandler=RequestHandler) as server:
    # def put(key, value):
    #     #        print(type(value))
    #     #        myba = bytearray(value)
    #     #        print(str(value.hex()))
    #     kv[key] = value
    #     return 0
    #
    #
    # server.register_function(put, 'put')
    #
    #
    # def get(key):
    #     if key in kv:
    #         return kv[key]
    #     else:
    #         return -1
    #
    #
    # server.register_function(get, 'get')
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
    server.register_instance(RawBlocks, allow_dotted_names=True)

    # Run the server's main loop
    server.serve_forever()
