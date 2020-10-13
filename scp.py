"""
Set of functions to receive DICOM from a sender and process them once
receipt is complete.
The general workflow is:
  - A DICOM storage class providor (SCP) is started
  - Files are received in to dcmstore/received dir
  - If no new images are received for a study after a set amount of time,
    the study is considered complete and moved to the dcmstore/queue folder
  - A polling function checks the queue folder for complete studies and
    processes them
  - Processed studies are moved to dcmstore/processed
"""

# ref https://pydicom.github.io/pynetdicom/dev/tutorials/create_scp.html

import os
from datetime import datetime
import logging
import threading
from pathlib import Path
from pynetdicom import (
  AE, debug_logger, evt, AllStoragePresentationContexts,
  ALL_TRANSFER_SYNTAXES
)

# Verification class for C-ECHO (https://pydicom.github.io/pynetdicom/stable/examples/verification.html)
from pynetdicom.sop_class import VerificationSOPClass


debug_logger()
LOGGER = logging.getLogger('pynetdicom')

"""
dict with
  key: 'dcmstore/received/{mrn}/{accnum}'
  val: datetime of last received file
"""
last_received_time = {}

# Preload with any studies left over from prior runs
received_pts = [x for x in Path('dcmstore/received').iterdir() if x.is_dir()]
for pt in received_pts:
  studies = [x for x in pt.iterdir() if x.is_dir()]
  for s in studies:
    last_received_time[s] = datetime.now()

def process_from_queue():
  """
  Process studies from queue folder.
  """
  threading.Timer(300, process_from_queue).start()
  queue_pts = [x for x in Path('dcmstore/queue').iterdir() if x.is_dir()]
  for pt in queue_pts:
    studies = [x for x in pt.iterdir() if x.is_dir()]
    ### if len(studies) > 0:
      ### DO SOMETHING with studies[0] here

process_from_queue()

def check_studies():
  """
  Checks q20sec for studies with no new images in >= 2 min
  Assume these stale studies have finished being sent
  Move from `received` => `queue` folder for further processing
  Remove empty dirs from `received` folder
  """
  threading.Timer(20.0, check_studies).start()
  stale_studies = [s for s in last_received_time if (datetime.now() - last_received_time[s]).total_seconds() >= 120]
  for old in stale_studies:
    new = 'dcmstore/queue'/old.relative_to('dcmstore/received')
    new.mkdir(parents=True, exist_ok=True)
    old.rename(new)
    last_received_time.pop(old)
    try:
      old.parent.rmdir()
    except OSError:
      """
      Dir not empty. Do nothing. The server may be receiving another study from
        the same patient and that study might still be in progress
      """

# Start timed function
check_studies()

def handle_store(event, storage_dir):
  """
  Handle EVT_C_STORE events
  Saves to:
    dcmstore/
      received/
        {mrn}/
          {accnum}/
            {series num}_{series desc}/   ###  If present  ##
              {SOPInstanceUID}.dcm
  """
  ds = event.dataset
  ds.file_meta = event.file_meta
  save_loc = storage_dir/ds.PatientID/ds.AccessionNumber
  last_received_time[save_loc] = datetime.now()

  if ds.SeriesNumber is not None:
    series_desc = str(ds.SeriesNumber).zfill(2)
    if "SeriesDescription" in ds:
      series_desc += '_' + ds.SeriesDescription.replace('/', '_')
    save_loc = save_loc/series_desc

  try:
    save_loc.mkdir(parents=True, exist_ok=True)
  except:
    # Unable to create output dir, return failure status
    return 0xC001

  save_loc = save_loc/ds.SOPInstanceUID
  # Because SOPInstanceUID includes several '.' you can't just use
  #   with_suffix or else it will replaces the portion of the UID that follows
  #   the last '.' with '.dcm', truncating the actual UID
  save_loc = save_loc.with_suffix(save_loc.suffix +'.dcm')
  ds.save_as(save_loc, write_like_original=False)

  return 0x0000

# Implement a handler for evt.EVT_C_ECHO (https://pydicom.github.io/pynetdicom/stable/examples/verification.html)
def handle_echo(event):
    """Handle a C-ECHO request event."""
    return 0x0000



# List of event handlers
handlers = [
  (evt.EVT_C_STORE, handle_store, [Path('dcmstore/received')]),(evt.EVT_C_ECHO, handle_echo)
]

ae = AE()

# Accept storage of all SOP classes
storage_sop_classes = [
  cx.abstract_syntax for cx in AllStoragePresentationContexts
]
for uid in storage_sop_classes:
  ae.add_supported_context(uid, ALL_TRANSFER_SYNTAXES)

ae.add_supported_context(VerificationSOPClass)

# Supposedly increases transfer speed
# ref: https://pydicom.github.io/pynetdicom/dev/examples/storage.html#storage-scp
ae.maximum_pdu_size = 0

ae.start_server(
  ('', 11112), # Start server on localhost port 11112
  block=True,  # Socket operates in blocking mode
  ae_title=os.environ['AE_TITLE'],
  evt_handlers=handlers
)
