#!/usr/bin/python

# FTP OAG Script
# Version 2 - maytech copy

# we only need the datetime class & the static function strptime from datetime module
#
# UPDATE 20170421 - SL (BT-85)
# - Removed natshistory.db file, this was causing performance issues
# - Removed hard-coded variables and added config file
# - Added a sort key on the sftp file list
# - Added logic to only process a limited set of files specified in the config file (MAX_BATCH_SIZE)

import re
import time
import os
import argparse
import logging
import subprocess
import paramiko
import ConfigParser


def ssh_login(in_host, in_user, in_keyfile):
        logger = logging.getLogger()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())  # This line can be removed when the host is added to the known_hosts file
        privkey = paramiko.RSAKey.from_private_key_file(in_keyfile)
        try:
                ssh.connect(in_host, username=in_user, pkey=privkey)
        except Exception, e:
                logger.exception('SSH CONNECT ERROR: %s' % (e))
                os._exit(1)
        return ssh


def run_virus_scan(vscanexe, option, filename):
    logger = logging.getLogger()
    logger.debug("Virus Scanning %s", filename)
    # do quarantine move using via the virus scanner

    virus_scan_return_code = subprocess.call([vscanexe, '--quiet', '--move=' + QUARANTINE_DIR, option, filename])

    logger.debug("Virus scan result %s", virus_scan_return_code)
    if virus_scan_return_code != 0:  # Exit script if virus scan exe fails
        logger.error('VIRUS SCAN FAILED %s', filename)
        return False
    else:
        logger.debug('Virus scan OK')
    return True
# end def run_virus_scan


def main():
        global QUARANTINE_DIR
        YYYYMMDDSTR = time.strftime("%Y%m%d")

        CONFIG_FILE = 'DMZ_Config.ini'
        CUSTOM_SECTION = 'sftp_nats_client_maytech'

        config = ConfigParser.ConfigParser()
        config.read(CONFIG_FILE)

        SSH_LANDING_DIR = re.sub("/*$", "/", config.get(CUSTOM_SECTION, 'SSH_LANDING_DIR'))
        DOWNLOAD_DIR = re.sub("/*$", "/", config.get(CUSTOM_SECTION, 'DOWNLOAD_DIR'))
        STAGING_DIR = re.sub("/*$", "/", config.get(CUSTOM_SECTION, 'STAGING_DIR'))
        ARCHIVE_DIR = re.sub("/*$", "/", config.get(CUSTOM_SECTION, 'ARCHIVE_DIR'))
        LOG_DIR = re.sub("/*$", "/", config.get(CUSTOM_SECTION, 'LOG_DIR'))
        SCRIPTS_DIR = re.sub("/*$", "/", config.get(CUSTOM_SECTION, 'SCRIPTS_DIR'))
        QUARANTINE_DIR = re.sub("/*$", "/", config.get(CUSTOM_SECTION, 'QUARANTINE_DIR'))
        SSH_REMOTE_HOST = config.get(CUSTOM_SECTION, 'SSH_REMOTE_HOST')
        SSH_REMOTE_USER = config.get(CUSTOM_SECTION, 'SSH_REMOTE_USER')
        SSH_PRIVATE_KEY = config.get(CUSTOM_SECTION, 'SSH_PRIVATE_KEY')
        NATS_FILE_REGEX = config.get(CUSTOM_SECTION, 'NATS_FILE_REGEX')
        NATS_DONE_FILE_REGEX = config.get(CUSTOM_SECTION, 'NATS_DONE_FILE_REGEX')
        VSCANEXE = config.get(CUSTOM_SECTION, 'VSCANEXE')
        VSCANOPT = config.get(CUSTOM_SECTION, 'VSCANOPT')
        MAX_BATCH_SIZE = int(config.get(CUSTOM_SECTION, 'MAX_BATCH_SIZE'))

        parser = argparse.ArgumentParser(description='NATS SFTP Downloader')
        parser.add_argument('-D', '--DEBUG',  default=False, action='store_true', help='Debug mode logging')

        args = parser.parse_args()
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        if args.DEBUG:
                logging.basicConfig(
                    filename=os.path.join(LOG_DIR, 'sftp_nats_'+YYYYMMDDSTR+'.log'),
                    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.DEBUG
                )
        else:
                logging.basicConfig(
                    filename=os.path.join(LOG_DIR, 'sftp_nats_' + YYYYMMDDSTR + '.log'),
                    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.INFO
                )

        logger = logging.getLogger()
        logger.info("Starting")
        status = 1

        # Main
        os.chdir(SCRIPTS_DIR)
        if not os.path.exists(DOWNLOAD_DIR):
                os.makedirs(DOWNLOAD_DIR)
        if not os.path.exists(ARCHIVE_DIR):
                os.makedirs(ARCHIVE_DIR)
        if not os.path.exists(STAGING_DIR):
                os.makedirs(STAGING_DIR)
        if not os.path.exists(QUARANTINE_DIR):
                os.makedirs(QUARANTINE_DIR)

        # process download folder for downloaded files and move to archive folder
        logger.debug("Scanning download folder %s", DOWNLOAD_DIR)
        for f in os.listdir(DOWNLOAD_DIR):
                logger.debug("File %s", f)
                match = re.search(NATS_DONE_FILE_REGEX, f, re.I)

                if match is not None:
                        filename = match.group(1)
                        logger.info("File %s has been downloaded %s file found", filename, f)
                        nf = os.path.join(ARCHIVE_DIR, filename)
                        lf = os.path.join(DOWNLOAD_DIR, filename)
                        lfd = os.path.join(DOWNLOAD_DIR, f)
                        os.rename(lf, nf)
                        logger.info("Archived %s", filename)
                        os.unlink(lfd)

        downloadcount = 0
        downloadtostagecount = 0
        logger.debug("Connecting via SSH")
        ssh = ssh_login(SSH_REMOTE_HOST, SSH_REMOTE_USER, SSH_PRIVATE_KEY)
        logger.debug("Connected")
        sftp = ssh.open_sftp()

        try:
                sftp.chdir(SSH_LANDING_DIR)

                files = sorted(sftp.listdir(), key=lambda x: sftp.stat(x).st_mtime)  # sort by modified date and get only limited batch

                for f in files:
                        match = re.search(NATS_FILE_REGEX, f, re.I)
                        download = True
                        if match is not None:
                            lf = os.path.join(DOWNLOAD_DIR, f)
                            slf = os.path.join(STAGING_DIR, f)

                            #protection against redownload
                            if os.path.isfile(slf) and os.path.getsize(slf) > 0 and os.path.getsize(slf) == sftp.stat(f).st_size:
                                    logger.info("File exists")
                                    download = False
                                    logger.debug("purge %s", f)
                                    sftp.remove(f)
                            if download:
                                    logger.info("Downloading %s to %s", f, slf)
                                    sftp.get(f, slf)  # remote, local
                                    downloadtostagecount += 1
                                    if os.path.isfile(slf) and os.path.getsize(slf) > 0 and os.path.getsize(slf) == sftp.stat(f).st_size:
                                            logger.debug("purge %s", f)
                                            sftp.remove(f)
                                    if downloadtostagecount >= MAX_BATCH_SIZE:
                                        logger.info("Max batch size reached (%s)", MAX_BATCH_SIZE)
                                        break

                # end for
        except:
                logger.exception("Failure")
                status = -2
    # end with

    # batch virus scan on STAGING_DIR for NATS
        logger.debug("before virus scan")
        if run_virus_scan(VSCANEXE, VSCANOPT, STAGING_DIR):
                for f in os.listdir(STAGING_DIR):
                        lf = os.path.join(DOWNLOAD_DIR, f)
                        sf = os.path.join(STAGING_DIR, f)
                        logger.debug("move %s from staging to download %s", sf, lf)
                        os.rename(sf, lf)
                        downloadcount += 1

        logger.info("Downloaded %s files", downloadcount)

        if downloadcount == 0:
                status = -1

        logger.info("Done Status %s", status)
        print status

# end def main

if __name__ == '__main__':
    main()
