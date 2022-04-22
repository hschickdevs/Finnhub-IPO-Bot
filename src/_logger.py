import logging
import os

# Start with fresh logfile
logfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log.txt')
if os.path.isfile(logfile):
    os.remove(logfile)

logging.basicConfig(filename=logfile, level=logging.DEBUG,
                    format='%(filename)s - %(asctime)s - %(levelname)s - %(message)s')

log = logging.getLogger(__name__)
