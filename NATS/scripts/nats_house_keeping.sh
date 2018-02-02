#!/bin/bash
#Maintaining 24hrs of NATS data only due to high file counts
#Clear Archive
find /u02/NATS/archive/nats/ -type f -mtime +1 -delete
#Crear Staging Directory 
find /u02/NATS/data/nats/ -type f -mtime +1 -delete
