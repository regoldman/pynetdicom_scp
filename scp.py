"""
Set of functions to receive DICOM from a sender
The general workflow is:
  - A DICOM storage class providor (SCP) is started
  - Files are received in to dcmstore/received dir
"""

# ref https://pydicom.github.io/pynetdicom/dev/tutorials/create_scp.html

import os
import logging
from pathlib import Path
from pynetdicom import (
  AE, debug_logger, evt, AllStoragePresentationContexts,
  ALL_TRANSFER_SYNTAXES
)
from pydicom import dcmread

# Verification class for C-ECHO (https://pydicom.github.io/pynetdicom/stable/examples/verification.html)
from pynetdicom.sop_class import VerificationSOPClass

debug_logger()
LOGGER = logging.getLogger('pynetdicom')

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
  # Because SOPInstanceUID includes several '.' you can't just use pathlib's
  #   with_suffix or else it will replace the portion of the UID that follows
  #   the last '.' with '.dcm', truncating the actual UID
  # Instead we add '.dcm' to what pathlib THINKS is the file suffix (that portion
  #   of the UID that follows the last .)
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

# Accept storage of all SOP classes that pynetdicom supports
storage_sop_classes = [
  cx.abstract_syntax for cx in AllStoragePresentationContexts
]
for uid in storage_sop_classes:
  ae.add_supported_context(uid, ALL_TRANSFER_SYNTAXES)

ae.add_supported_context(VerificationSOPClass)

# Supposedly increases transfer speed
# ref: https://pydicom.github.io/pynetdicom/dev/examples/storage.html#storage-scp
ae.maximum_pdu_size = 0

# Start server on localhost, port 11112 (this is the port internal
#   to the docker container. The port that the network sees is the
#   host port specified in the .env file.)
ae.start_server(
  ('', 11112),
  block=True,  # Socket operates in blocking mode
  ae_title=os.environ['AE_TITLE'], # specified in the .env file
  evt_handlers=handlers
)
