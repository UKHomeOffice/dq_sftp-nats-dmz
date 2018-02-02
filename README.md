### Background 
This application originated from  code written to collect OAG flight schedules via a 3rd party SFTP provider, a regex change was made and the code re-purposed to process NATS data.

Due to only one source of data and a business requirement to service all environments with a live feed, the code `sftp_nats_prod1.py` firstly downloads and virus scans the files from the remote landing directory and places them on the server. At this point the data is now availible for use. The same script then re-uploads the files it downloaded back to the third party SFTP site for use by other environments. eg. dev / pre-prod

`sftp_nats_prod2.py` takes all the files that `sftp_nats_prod1.py` re-uploaded, downloads them again re-uploads them again to an arbitary amount of extra destinations on the remote SFTP provider, in this case 2, Dev / Preprod.

`sftp_nats_client_maytech.py` is placed on any client server which needs to collect the data uploaded by `sftp_nats_prod2.py`


A number of limiting factors gave birth to the code above.
These include:
- No ability to simply sync the directories on the upstream SFTP site 
(which would have eliminated almost all code entirely)

- Suppliers still operating via FTP and SFTP

#### Legacy Code
Streaming / MQ systems are planned to process this type of feed in future, further the business requirement of servicing multiple environments no longer exists for this code base. 
