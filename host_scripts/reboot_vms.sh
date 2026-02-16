#!/bin/bash
# Reboot each given VM (sends reboot signal to guest; one action per host).

for vmname in "$@"
do
    echo "rebooting $vmname"
    virsh reboot "$vmname"
    echo "reboot sent for $vmname"
done
