#!/usr/bin/env bash

setup_ssh() {
  # Create an SSH public key so that local SSH works without a password.
  local _ssh_key=~/.ssh/id_rsa
  rm -f ${_ssh_key}*
  ssh-keygen -t rsa -N "" -f $_ssh_key
  # Ensure a new line for the new key to start on.
  # See: https://issues.apache.org/jira/browse/AURORA-1728
  echo >> ~/.ssh/authorized_keys
  cat ${_ssh_key}.pub >> ~/.ssh/authorized_keys
}

setup_ssh