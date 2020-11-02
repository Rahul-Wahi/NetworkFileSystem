from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import threading
import xmlrpc.client
import base64
import pickle, logging
from memoryfs_client import BLOCK_SIZE, TOTAL_NUM_BLOCKS


#### BLOCK LAYER

class DiskBlocks():
    def __init__(self):
        # This class stores the raw block array
        self.block = []
        self.LOCKED = "LOCKED"
        self.UNLOCKED = "UNLOCKED"
        self.lock = threading.Lock()
        # Initialize raw blocks
        for i in range(0, TOTAL_NUM_BLOCKS):
            putdata = bytearray(BLOCK_SIZE)
            self.block.insert(i, putdata)

    def ReadSetBlock(self, block_number, data):
        self.lock.acquire()
        try:
            value = self.Get(block_number)
            self.Put(block_number, data)
        finally:
            self.lock.release()
            return value

    ## Put: interface to write a raw block of data to the block indexed by block number
    ## Blocks are padded with zeroes up to BLOCK_SIZE

    def Put(self, block_number, block_data):
        if isinstance(block_data, xmlrpc.client.Binary):
            block_data = block_data.data
        print(block_number)
        print(" , ")
        print(block_data)
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


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)


# Create server
with SimpleXMLRPCServer(('localhost', 8000),
                        requestHandler=RequestHandler, allow_none=True) as server:

    # Initialize file system data
    logging.info('Initializing data structures...')
    RawBlocks = DiskBlocks()

    server.register_instance(RawBlocks, allow_dotted_names=True)

    # Run the server's main loop
    server.serve_forever()
