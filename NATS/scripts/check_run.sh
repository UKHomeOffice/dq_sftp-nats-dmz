#!/bin/bash

SCRIPT_TO_RUN=$1

if [[ $SCRIPT_TO_RUN == '' ]]; then 
  echo 'Script parameter required'
  exit 1
fi

PIDFILE=$( echo ${SCRIPT_TO_RUN}.pid )

if [ -e "${PIDFILE}" ] && (ps -u $(whoami) -opid= |
                           grep -P "^\s*$(cat ${PIDFILE})$" &> /dev/null); then
  echo "Already running."
  exit 99
fi

$SCRIPT_TO_RUN &
echo Running $SCRIPT_TO_RUN
echo $! > "${PIDFILE}"
chmod 644 "${PIDFILE}"
