# pynetdicom_scp

## Getting started

Use <code>.env_sample</code> as a template to create a .env file in the same
directory as Dockerfile

Run
```
>> docker-compose build
>> docker-compose up
```

Uses
```
* Starts a DICOM-compliant listener with port/AE_TITLE as specified in .env
* Receives DICOMs to dcmstore/received/{MRN}/{Acc #}/{Series #}_{Series Description}/{UID}.dcm

